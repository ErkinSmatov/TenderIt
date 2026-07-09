import json
import secrets
from typing import Optional

import redis.asyncio as aioredis

from app.config import settings


async def get_redis():
    """Async generator yielding a Redis client. Closes connection on exit."""
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def store_refresh_token(redis: aioredis.Redis, user_id: int, token: str) -> None:
    """Store refresh token in Redis with 7-day TTL."""
    await redis.setex(f"refresh_token:{user_id}", 604800, token)


async def get_refresh_token(redis: aioredis.Redis, user_id: int) -> str | None:
    """Retrieve stored refresh token for user. Returns None if not found."""
    return await redis.get(f"refresh_token:{user_id}")


async def rotate_refresh_token(redis: aioredis.Redis, user_id: int, new_token: str) -> None:
    """Atomically replace the stored refresh token for user.

    Uses a Redis pipeline (MULTI/EXEC) so there is no window where both the
    old and the new token are simultaneously valid.  The old key is deleted and
    the new token is written with a fresh 7-day TTL in a single round-trip.
    """
    key = f"refresh_token:{user_id}"
    pipe = redis.pipeline()
    pipe.delete(key)
    pipe.setex(key, 604800, new_token)
    await pipe.execute()


async def revoke_refresh_token(redis: aioredis.Redis, user_id: int) -> None:
    """Delete refresh token from Redis (used on logout)."""
    await redis.delete(f"refresh_token:{user_id}")


# ---------------------------------------------------------------------------
# Password-reset token helpers (AUTH-03)
# ---------------------------------------------------------------------------

_RESET_TOKEN_TTL = 900  # 15 minutes (A1)


async def create_reset_token(redis: aioredis.Redis, user_id: int) -> str:
    """Generate a 32-byte URL-safe token, store reset:{token} -> user_id with 900s TTL."""
    token = secrets.token_urlsafe(32)
    await redis.setex(f"reset:{token}", _RESET_TOKEN_TTL, str(user_id))
    return token


async def consume_reset_token(redis: aioredis.Redis, token: str) -> Optional[int]:
    """Atomically consume a reset token via GETDEL.

    Returns user_id as int if the token existed, None otherwise.
    Single-use: the key is deleted as part of the read (T-02-04-01).
    """
    value = await redis.getdel(f"reset:{token}")
    return int(value) if value else None


# ---------------------------------------------------------------------------
# Phase 5 — goszakup portal session + submission confirm helpers (D-05-02, D-05-06)
# ---------------------------------------------------------------------------

# TTL constants (T-05-06 mitigation: hard TTL prevents unbounded session persistence)
_GOSZAKUP_SESSION_TTL = 72000  # 20 hours — goszakup PHP session lifetime
_CONFIRM_TTL = 900             # 15 minutes — confirm:{app_id} pending window (D-05-06)


async def store_goszakup_session(
    redis: aioredis.Redis,
    user_id: int,
    phpsessid: str,
    csrf: str,
    application_id: int,
    tender_buy_id: int,
) -> None:
    """Store goszakup portal session data in Redis for ARQ worker.

    Key: goszakup_session:{user_id}
    TTL: 72000s (20h) — hard limit per T-05-06

    Data is JSON-serialized dict: {phpsessid, csrf, application_id, tender_buy_id}.
    Caller must NOT log phpsessid/csrf values (T-05-03 mitigation).
    """
    data = {
        "phpsessid": phpsessid,
        "csrf": csrf,
        "application_id": application_id,
        "tender_buy_id": tender_buy_id,
    }
    await redis.setex(
        f"goszakup_session:{user_id}",
        _GOSZAKUP_SESSION_TTL,
        json.dumps(data),
    )


async def get_goszakup_session(redis: aioredis.Redis, user_id: int) -> Optional[dict]:
    """Read goszakup session for user. Returns parsed dict or None if absent/expired.

    decode_responses=True on the Redis client means the value is already a str;
    no manual decode needed.
    """
    raw = await redis.get(f"goszakup_session:{user_id}")
    return json.loads(raw) if raw else None


async def set_confirm_pending(redis: aioredis.Redis, application_id: int) -> None:
    """Mark an application as awaiting user confirmation.

    Key: confirm:{application_id}  Value: "pending"  TTL: 900s (15 min)
    Used by ARQ worker after sending Telegram notification (D-05-06).
    """
    await redis.setex(f"confirm:{application_id}", _CONFIRM_TTL, "pending")


async def update_confirm(redis: aioredis.Redis, application_id: int, value: str) -> None:
    """Update confirm key to 'yes' or 'no' WITHOUT changing the TTL.

    Uses SET (not SETEX) — the remaining TTL from set_confirm_pending is preserved.
    The key expires naturally after 15 minutes regardless of user response timing.
    """
    await redis.set(f"confirm:{application_id}", value)


async def get_confirm(redis: aioredis.Redis, application_id: int) -> Optional[str]:
    """Read current confirm value. Returns 'pending', 'yes', 'no', or None if expired/absent."""
    return await redis.get(f"confirm:{application_id}")
