"""
Integration tests for POST /api/auth/refresh and POST /api/auth/logout.

Redis is provided via a fakeredis.aioredis FakeRedis instance injected through
app.dependency_overrides in a session-scoped fixture.

Email addresses include a UUID suffix so tests are idempotent across multiple
runs against a real (non-reset) Postgres instance.
"""
import uuid
from datetime import datetime, timedelta, timezone

import fakeredis.aioredis
import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services.redis_service import get_redis

REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"
REFRESH_URL = "/api/auth/refresh"
LOGOUT_URL = "/api/auth/logout"

VALID_PASSWORD = "securepassword123"


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def fake_redis_instance():
    """A single FakeRedis instance reused across the test session."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest_asyncio.fixture(scope="session")
async def refresh_client(fake_redis_instance):
    """HTTP client with FakeRedis injected as the get_redis dependency."""

    async def _override_get_redis():
        yield fake_redis_instance

    app.dependency_overrides[get_redis] = _override_get_redis
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.pop(get_redis, None)


async def _register_and_login(client, email: str) -> dict:
    """Helper: register + login, return {"access_token": ..., "refresh_token": ...}."""
    reg = await client.post(REGISTER_URL, json={"email": email, "password": VALID_PASSWORD})
    assert reg.status_code == 201, f"Register failed: {reg.text}"
    return {
        "access_token": reg.cookies.get("access_token"),
        "refresh_token": reg.cookies.get("refresh_token"),
    }


# ---------------------------------------------------------------------------
# /api/auth/refresh tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_success_rotates_tokens(refresh_client):
    """Happy path: refresh issues new access + refresh tokens, old refresh token is revoked."""
    email = unique_email("refresh_ok")
    tokens = await _register_and_login(refresh_client, email)
    old_access = tokens["access_token"]
    old_refresh = tokens["refresh_token"]
    assert old_refresh is not None

    resp = await refresh_client.post(
        REFRESH_URL,
        cookies={"refresh_token": old_refresh, "access_token": old_access},
    )
    assert resp.status_code == 204

    new_access = resp.cookies.get("access_token")
    new_refresh = resp.cookies.get("refresh_token")
    assert new_access is not None
    assert new_refresh is not None
    # New tokens must differ from old ones
    assert new_access != old_access
    assert new_refresh != old_refresh


@pytest.mark.asyncio
async def test_refresh_with_replayed_old_token_returns_401(refresh_client):
    """Replay protection: after a successful refresh (T1 -> T2), replaying T1 returns 401."""
    email = unique_email("replay")
    tokens = await _register_and_login(refresh_client, email)
    old_refresh = tokens["refresh_token"]
    assert old_refresh is not None

    # First refresh succeeds (T1 -> T2)
    resp1 = await refresh_client.post(
        REFRESH_URL,
        cookies={"refresh_token": old_refresh},
    )
    assert resp1.status_code == 204

    # Replaying T1 must return 401
    resp2 = await refresh_client.post(
        REFRESH_URL,
        cookies={"refresh_token": old_refresh},
    )
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(refresh_client):
    """Missing refresh_token cookie returns 401."""
    resp = await refresh_client.post(REFRESH_URL)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_expired_token_returns_401(refresh_client):
    """Refresh token with past expiry returns 401."""
    email = unique_email("expired")
    await _register_and_login(refresh_client, email)

    # Craft an already-expired refresh token
    expired_token = jwt.encode(
        {
            "sub": "9999",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
            "type": "refresh",
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    resp = await refresh_client.post(
        REFRESH_URL,
        cookies={"refresh_token": expired_token},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_in_refresh_cookie_returns_401(refresh_client):
    """Submitting an access token (type != 'refresh') to /refresh returns 401."""
    email = unique_email("wrongtype")
    tokens = await _register_and_login(refresh_client, email)

    # access_token has no "type" claim — should fail the type check
    resp = await refresh_client.post(
        REFRESH_URL,
        cookies={"refresh_token": tokens["access_token"]},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /api/auth/logout tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_clears_redis_and_cookies(refresh_client):
    """Logout deletes the Redis key; subsequent refresh attempt returns 401."""
    email = unique_email("logout_ok")
    tokens = await _register_and_login(refresh_client, email)
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]
    assert access and refresh

    # Logout requires a valid access_token
    resp = await refresh_client.post(
        LOGOUT_URL,
        cookies={"access_token": access, "refresh_token": refresh},
    )
    assert resp.status_code == 204

    # Subsequent refresh must fail (Redis key was deleted)
    resp2 = await refresh_client.post(
        REFRESH_URL,
        cookies={"refresh_token": refresh},
    )
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_logout_without_auth_returns_401(refresh_client):
    """Calling /logout without a valid access_token returns 401."""
    resp = await refresh_client.post(LOGOUT_URL)
    assert resp.status_code == 401
