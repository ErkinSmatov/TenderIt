"""Telegram webhook router — receive and process callback_query updates.

Security invariants:
  T-05-31: Requests without a matching X-Telegram-Bot-Api-Secret-Token header → 403.
  T-05-30: The callback chat_id must match the application owner's telegram_chat_id.
           Mismatches are silently ignored (do not leak existence of the resource).
  T-05-32: Immediate enqueue uses the same _job_id=f"submit:{app_id}" as the 15-min
           fallback, ensuring ARQ deduplicates them — no double submit.

Endpoint:
  POST /api/telegram/webhook  (prefix "/api" applied by main.py include_router)

Telegram set_webhook registration is performed in the FastAPI lifespan (main.py).

Reference: 05-RESEARCH.md lines 526-564 (Pattern 4: webhook endpoint + set_webhook).
"""

from __future__ import annotations

import logging

import telegram
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update

from app.config import settings
from app.db import get_db
from app.models.application import Application
from app.models.user import User
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
    incoming_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if incoming_secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    body = await request.json()
    update = Update.de_json(body, bot=None)

    if not update.callback_query:
        # Non-callback update (e.g. plain message) — accept silently
        return {"ok": True}

    query = update.callback_query
    data = query.data or ""

    # Parse "confirm:{action}:{app_id}"
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "confirm":
        return {"ok": True}

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
    caller_chat_id = query.from_user.id if query.from_user else None
    owner = await get_user_by_id(db, app_obj.user_id)
    if owner is None or owner.telegram_chat_id != caller_chat_id:
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
        logger.info("telegram_webhook: app %s confirmed YES → immediate submit enqueued", app_id)
    elif action == "no":
        await update_confirm(redis, app_id, "no")
        logger.info("telegram_webhook: app %s confirmed NO → cancelled", app_id)
    else:
        logger.warning("telegram_webhook: unknown action %r for app %s", action, app_id)

    return {"ok": True}
