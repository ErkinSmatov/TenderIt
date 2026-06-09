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
