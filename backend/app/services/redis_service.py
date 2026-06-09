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


async def revoke_refresh_token(redis: aioredis.Redis, user_id: int) -> None:
    """Delete refresh token from Redis (used on logout)."""
    await redis.delete(f"refresh_token:{user_id}")
