"""Integration tests for the password-reset flow (AUTH-03).

Coverage:
  1. forgot_password_known_email_creates_redis_token_and_returns_202
  2. forgot_password_unknown_email_returns_202_no_token_created
  3. reset_password_valid_token_updates_hashed_password_and_returns_204
  4. reset_password_replay_returns_400
  5. reset_password_invalid_token_returns_400
  6. reset_password_short_password_returns_422
  7. email_service_debug_mode_does_not_call_resend
"""

import uuid

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from unittest.mock import MagicMock

from app.main import app
from app.models.user import User
from app.services.auth_service import hash_password
from app.services.redis_service import get_redis


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def fake_redis():
    """Provide an in-memory fakeredis client for the duration of each test."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def reset_client(fake_redis):
    """HTTP client with fakeredis wired in via dependency override."""

    async def override_get_redis():
        yield fake_redis

    app.dependency_overrides[get_redis] = override_get_redis
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, fake_redis
    app.dependency_overrides.pop(get_redis, None)


@pytest_asyncio.fixture
async def registered_user():
    """Create and commit a real user row; clean up after the test."""
    from app.db import AsyncSessionLocal

    email = f"reset_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "Secure1234!"
    user_id = None

    async with AsyncSessionLocal() as session:
        async with session.begin():
            user = User(
                email=email,
                hashed_password=hash_password(password),
                is_active=True,
            )
            session.add(user)
        await session.refresh(user)
        user_id = user.id

    yield email, password, user_id

    # Cleanup: delete the user after the test
    async with AsyncSessionLocal() as session:
        async with session.begin():
            u = await session.get(User, user_id)
            if u:
                await session.delete(u)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forgot_password_known_email_creates_redis_token_and_returns_202(
    reset_client, registered_user
):
    """A known email triggers a Redis reset token and returns 202."""
    client, fake_redis = reset_client
    email, _, _ = registered_user

    resp = await client.post("/api/auth/forgot-password", json={"email": email})

    assert resp.status_code == 202
    assert "зарегистрирован" in resp.json()["message"]

    # At least one reset:* key must have been created
    keys = await fake_redis.keys("reset:*")
    assert len(keys) >= 1, "Expected a reset token to be created in Redis"


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_returns_202_no_token_created(
    reset_client,
):
    """An unknown email still returns 202 (no enumeration); no Redis key created."""
    client, fake_redis = reset_client

    resp = await client.post(
        "/api/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )

    assert resp.status_code == 202
    assert "зарегистрирован" in resp.json()["message"]

    keys = await fake_redis.keys("reset:*")
    assert len(keys) == 0, "No reset token should be created for unknown email"


@pytest.mark.asyncio
async def test_reset_password_valid_token_updates_hashed_password_and_returns_204(
    reset_client, registered_user
):
    """A valid reset token causes password update and returns 204."""
    from app.db import AsyncSessionLocal
    from app.services.auth_service import verify_password

    client, fake_redis = reset_client
    email, old_password, user_id = registered_user

    # Plant a reset token directly
    token = "a" * 43  # secrets.token_urlsafe(32) produces ~43 chars
    await fake_redis.setex(f"reset:{token}", 900, str(user_id))

    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "NewSecure99!"},
    )

    assert resp.status_code == 204

    # Token must be consumed
    remaining = await fake_redis.get(f"reset:{token}")
    assert remaining is None, "Reset token should be deleted after use"

    # Password should be updated in DB — use a fresh session to see committed data
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        db_user = result.scalar_one()
        assert verify_password("NewSecure99!", db_user.hashed_password), (
            "hashed_password was not updated"
        )


@pytest.mark.asyncio
async def test_reset_password_replay_returns_400(
    reset_client, registered_user
):
    """Using the same token a second time returns 400 (single-use enforcement)."""
    client, fake_redis = reset_client
    _, _, user_id = registered_user

    token = "b" * 43
    await fake_redis.setex(f"reset:{token}", 900, str(user_id))

    # First use — should succeed
    resp1 = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "FirstReset1!"},
    )
    assert resp1.status_code == 204

    # Second use — must fail
    resp2 = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "SecondReset2!"},
    )
    assert resp2.status_code == 400
    assert "недействительна" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_reset_password_invalid_token_returns_400(reset_client):
    """A token that was never stored returns 400."""
    client, fake_redis = reset_client

    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": "c" * 43, "new_password": "SomePassword1!"},
    )

    assert resp.status_code == 400
    assert "недействительна" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reset_password_short_password_returns_422(reset_client):
    """A new_password shorter than 8 characters returns 422 (validation error)."""
    client, fake_redis = reset_client

    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": "d" * 43, "new_password": "short"},
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_email_service_debug_mode_does_not_call_resend(monkeypatch):
    """In debug mode, send_password_reset_email must NOT invoke resend.Emails.send."""
    import resend

    send_mock = MagicMock(side_effect=RuntimeError("resend should not be called in debug"))
    monkeypatch.setattr(resend.Emails, "send", send_mock)

    # Patch settings.debug to True (it already is by default, but be explicit)
    from app.config import settings
    monkeypatch.setattr(settings, "debug", True)

    from app.services.email_service import send_password_reset_email

    # Should not raise
    await send_password_reset_email("user@example.com", "http://localhost:3000/reset-password?token=abc")

    send_mock.assert_not_called()
