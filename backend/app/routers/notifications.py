"""Notifications router — Phase 6, NOTIF-04: Telegram account linking.

Endpoints (all require JWT authentication via get_current_user):
  POST   /notifications/telegram/link-token  — generate a 15-min deep-link token
  GET    /notifications/status               — check Telegram connection status
  DELETE /notifications/telegram             — disconnect Telegram account

Security invariants:
  IDOR-safe: user_id is ALWAYS derived from the JWT (current_user), never from request body.
  T-06-01: secrets.token_urlsafe(32) = 43-char URL-safe token with 256-bit entropy.
  T-06-02: Token cleared on first successful /start use (handled in telegram_webhook.py).
  T-06-03: DELETE clears telegram_chat_id AND telegram_link_token (full disconnect).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/notifications/telegram/link-token")
async def create_telegram_link_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a Telegram deep-link token for account linking.

    Creates a 43-character URL-safe token (secrets.token_urlsafe(32)) valid for 15 minutes.
    Stores token + expiry on the current user. Returns a deep-link URL to open the bot.

    Security: T-06-01 — 256-bit entropy token stored in DB with unique index.
    """
    token = secrets.token_urlsafe(32)
    current_user.telegram_link_token = token
    current_user.telegram_link_token_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=15
    )
    await db.commit()

    deep_link = f"https://t.me/{settings.telegram_bot_username}?start={token}"
    return {"deep_link": deep_link}


@router.get("/notifications/status")
async def get_notification_status(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return current Telegram connection status for the authenticated user.

    Note: does NOT require db dependency — get_current_user already loads the user.
    T-06-06: Returns telegram_chat_id to the authenticated user only (JWT-scoped).
    """
    return {
        "telegram_connected": current_user.telegram_chat_id is not None,
        "telegram_chat_id": current_user.telegram_chat_id,
    }


@router.delete("/notifications/telegram", status_code=204)
async def disconnect_telegram(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Disconnect Telegram account from the authenticated user.

    Clears telegram_chat_id, telegram_link_token, and telegram_link_token_expires_at.
    Security: T-06-03 — user derived from JWT only; cannot affect other users.
    """
    current_user.telegram_chat_id = None
    current_user.telegram_link_token = None
    current_user.telegram_link_token_expires_at = None
    await db.commit()
    return Response(status_code=204)
