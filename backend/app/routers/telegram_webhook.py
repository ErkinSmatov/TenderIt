"""Telegram webhook router — receive and process callback_query updates.

Security invariants:
  T-05-31: Requests without a matching X-Telegram-Bot-Api-Secret-Token header → 403.
  T-05-30: The callback chat_id must match the application owner's telegram_chat_id.
           Mismatches are silently ignored (do not leak existence of the resource).
  T-05-32: Immediate enqueue uses the same _job_id=f"submit:{app_id}" as the 15-min
           fallback, ensuring ARQ deduplicates them — no double submit.
  T-07-01: disc:participate IDOR check — caller_chat_id must match match owner's telegram_chat_id.
  T-07-02: disc:skip IDOR check — same pattern as T-07-01.
  T-07-05: disc:* callbacks benefit from T-05-31 secret check automatically (same handler).

Endpoint:
  POST /api/telegram/webhook  (prefix "/api" applied by main.py include_router)

Telegram set_webhook registration is performed in the FastAPI lifespan (main.py).

Reference: 05-RESEARCH.md lines 526-564 (Pattern 4: webhook endpoint + set_webhook).
Reference: 07-RESEARCH.md pitfall 2 (guard must accept both 'confirm' and 'disc').
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import telegram
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update

from app.config import settings
from app.db import get_db
from app.models.application import Application
from app.models.tender_match import TenderMatch
from app.models.user import User
from app.services.application_service import create_discovery_draft
from app.services.redis_service import get_redis, update_confirm

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: load application by id (owner-unfiltered — this is a background job context)
# ---------------------------------------------------------------------------


async def get_application_by_id(
    db: AsyncSession, application_id: int
) -> Application | None:
    """Fetch an Application by id only (no user_id filter — used by background webhook).

    The IDOR check in this router is done via telegram chat_id comparison,
    not SQL filtering, because the user is identified by Telegram chat_id
    rather than a JWT token.
    """
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Fetch a User by id."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_tender_match_by_id(
    db: AsyncSession, match_id: int
) -> TenderMatch | None:
    """Fetch TenderMatch by id without user filter.

    IDOR check is performed via telegram_chat_id comparison (T-07-01, T-07-02),
    NOT via SQL filtering — same pattern as get_application_by_id.
    """
    result = await db.execute(
        select(TenderMatch).where(TenderMatch.id == match_id)
    )
    return result.scalar_one_or_none()


async def enqueue_submit(redis, application_id: int) -> None:
    """Enqueue auto_submit_application immediately with dedup job_id.

    Uses the same _job_id=f"submit:{application_id}" as the 15-min fallback job
    so that ARQ deduplicates them — only one job runs (T-05-32).
    """
    await redis.enqueue_job(
        "auto_submit_application",
        application_id,
        _job_id=f"submit:{application_id}",
    )
    logger.info(
        "telegram_webhook: enqueued immediate submit for app %s (job dedup active)",
        application_id,
    )


# ---------------------------------------------------------------------------
# Helper: handle /start TOKEN message for Telegram account linking (Phase 6, NOTIF-04)
# ---------------------------------------------------------------------------


async def _handle_start_command(message, db: AsyncSession) -> None:
    """Process a /start TOKEN message to link a Telegram account to TenderIt.

    T-06-04: Runs after T-05-31 secret guard — all calls to this function are already
    authenticated by Telegram. The function is called only for message updates with text.

    Flow:
      1. Parse token from "/start TOKEN" — returns early if not a /start command or no token.
      2. Look up User by telegram_link_token.
      3. Check expiry — if expired, send error message, clear token fields, return.
      4. On success — set telegram_chat_id, clear token fields, send confirmation.

    Security:
      T-06-01: token has 256-bit entropy (secrets.token_urlsafe(32)) — not guessable.
      T-06-02: token cleared on first successful use — cannot be replayed.
      T-06-05: timezone-aware comparison prevents naive datetime TypeErrors.
    """
    text = message.text or ""
    # T-06-05 / Pitfall 1: "/start " with trailing space is mandatory — plain /start returns early
    if not text.startswith("/start "):
        return
    token = text[7:].strip()
    if not token:
        return

    chat_id = message.from_user.id if message.from_user else None
    if not chat_id:
        return

    result = await db.execute(select(User).where(User.telegram_link_token == token))
    user = result.scalar_one_or_none()

    async with telegram.Bot(settings.telegram_bot_token) as bot:
        if user is None:
            await bot.send_message(
                chat_id=chat_id,
                text="Ссылка не найдена. Зайдите в TenderIt и получите новую.",
            )
            return

        # T-06-05: timezone-aware expiry comparison — prevents naive/aware TypeError
        now = datetime.now(timezone.utc)
        if user.telegram_link_token_expires_at and user.telegram_link_token_expires_at < now:
            # Expired — clear token but do NOT set telegram_chat_id
            user.telegram_link_token = None
            user.telegram_link_token_expires_at = None
            await db.commit()
            await bot.send_message(
                chat_id=chat_id,
                text="Ссылка устарела. Зайдите в TenderIt и получите новую ссылку.",
            )
            return

        # Success: link the account — T-06-02: clear token to prevent replay
        user.telegram_chat_id = chat_id
        user.telegram_link_token = None
        user.telegram_link_token_expires_at = None
        await db.commit()
        await bot.send_message(
            chat_id=chat_id,
            text="Telegram успешно подключён к TenderIt ✓",
        )


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive Telegram callback_query updates for Да/Нет confirmation.

    Security:
      - Verifies X-Telegram-Bot-Api-Secret-Token header (T-05-31).
      - Verifies callback chat_id matches application owner (T-05-30).
      - Stable _job_id deduplicates with 15-min fallback (T-05-32).
    """
    # T-05-31: Verify webhook secret
    # Guard: reject if either side is empty — prevents auth bypass when secret is unconfigured.
    incoming_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not incoming_secret or not settings.telegram_webhook_secret or incoming_secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    body = await request.json()
    update = Update.de_json(body, bot=None)

    if not update.callback_query:
        # Phase 6: handle /start TOKEN message for Telegram account linking (NOTIF-04).
        # WR-02: Only dispatch for /start commands — plain messages are ignored here.
        # The handler still guards internally but pre-filtering avoids unnecessary calls.
        if update.message and update.message.text and update.message.text.startswith("/start"):
            await _handle_start_command(update.message, db)
        return {"ok": True}

    query = update.callback_query
    data = query.data or ""

    # Parse "{prefix}:{action}:{id}" — accept "confirm" and "disc" prefixes
    # Research pitfall 2: original guard only accepted "confirm"; "disc:*" was silently dropped.
    parts = data.split(":")
    if len(parts) != 3 or parts[0] not in ("confirm", "disc"):
        return {"ok": True}

    if parts[0] == "confirm":
        action = parts[1]  # "yes" or "no"
        try:
            app_id = int(parts[2])
        except ValueError:
            return {"ok": True}

        # Load application
        app_obj = await get_application_by_id(db, app_id)
        if app_obj is None:
            logger.warning("telegram_webhook: app %s not found, ignoring callback", app_id)
            return {"ok": True}

        # T-05-30: IDOR check — caller's chat_id must match app owner's telegram_chat_id
        # CR-03: caller_chat_id is None check prevents None==None bypass for unlinked users.
        caller_chat_id = query.from_user.id if query.from_user else None
        owner = await get_user_by_id(db, app_obj.user_id)
        if caller_chat_id is None or owner is None or owner.telegram_chat_id != caller_chat_id:
            logger.warning(
                "telegram_webhook: IDOR attempt — app %s owner chat_id=%s, caller=%s",
                app_id,
                owner.telegram_chat_id if owner else None,
                caller_chat_id,
            )
            return {"ok": True}

        # Get ARQ redis pool from app state
        redis = request.app.state.arq_redis

        if action == "yes":
            await update_confirm(redis, app_id, "yes")
            await enqueue_submit(redis, app_id)
            logger.info(
                "telegram_webhook: app %s confirmed YES → immediate submit enqueued", app_id
            )
        elif action == "no":
            await update_confirm(redis, app_id, "no")
            logger.info("telegram_webhook: app %s confirmed NO → cancelled", app_id)
        else:
            logger.warning("telegram_webhook: unknown action %r for app %s", action, app_id)

        # CR-02: Acknowledge the callback to dismiss the Telegram button loading state.
        # Without this, Telegram shows "Bot didn't respond" on every Да/Нет press.
        try:
            async with telegram.Bot(settings.telegram_bot_token) as bot:
                await bot.answer_callback_query(callback_query_id=query.id)
        except Exception:
            pass  # Non-fatal — same pattern as disc branch

    elif parts[0] == "disc":
        disc_action = parts[1]  # "participate" or "skip"
        try:
            match_id = int(parts[2])
        except ValueError:
            return {"ok": True}

        # T-07-01 / T-07-02: IDOR check via Telegram chat_id
        match_obj = await get_tender_match_by_id(db, match_id)
        if match_obj is None:
            logger.warning("telegram_webhook: disc match %s not found", match_id)
            return {"ok": True}

        # CR-03: caller_chat_id is None check prevents None==None bypass for unlinked users.
        caller_chat_id = query.from_user.id if query.from_user else None
        match_owner = await get_user_by_id(db, match_obj.user_id)
        if caller_chat_id is None or match_owner is None or match_owner.telegram_chat_id != caller_chat_id:
            logger.warning(
                "telegram_webhook: IDOR attempt on disc match %s — owner_chat=%s caller=%s",
                match_id,
                match_owner.telegram_chat_id if match_owner else None,
                caller_chat_id,
            )
            return {"ok": True}  # T-07-05: silent ignore — same pattern as confirm IDOR

        if disc_action == "participate":
            app_obj = await create_discovery_draft(db, match_obj.user_id, match_obj.tender_id)
            match_obj.status = "participating"
            match_obj.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()
            logger.info(
                "telegram_webhook: disc participate — match %s → app %s created",
                match_id,
                app_obj.id,
            )
        elif disc_action == "skip":
            match_obj.status = "skipped"
            match_obj.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()
            logger.info("telegram_webhook: disc skip — match %s", match_id)
            # Delete the notification message so it disappears from the chat
            try:
                async with telegram.Bot(settings.telegram_bot_token) as bot:
                    await bot.answer_callback_query(callback_query_id=query.id)
                    if query.message:
                        await bot.delete_message(
                            chat_id=query.message.chat_id,
                            message_id=query.message.message_id,
                        )
            except Exception:
                pass  # Non-fatal — message may already be deleted or too old
            return {"ok": True}
        else:
            logger.warning(
                "telegram_webhook: unknown disc action %r for match %s", disc_action, match_id
            )

        # Acknowledge the callback to dismiss the Telegram button loading state
        try:
            async with telegram.Bot(settings.telegram_bot_token) as bot:
                await bot.answer_callback_query(callback_query_id=query.id)
        except Exception:
            pass  # Non-fatal — UI button will stop spinning after timeout

    return {"ok": True}
