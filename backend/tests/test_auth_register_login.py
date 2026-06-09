"""
Integration tests for POST /api/auth/register and POST /api/auth/login.

Uses the function-scoped `auth_client` fixture (avoids session-level asyncpg teardown issues).
Redis calls in register/login are mocked via monkeypatching store_refresh_token so tests
run without a live Redis instance.

Email addresses include a UUID suffix so tests are idempotent across multiple runs
against a real (non-reset) Postgres instance.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"

VALID_PASSWORD = "securepassword123"


def unique_email(prefix: str = "user") -> str:
    """Generate a test-run-unique email address."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_success_201(auth_client):
    """Happy-path registration: returns 201, body has user_id + email, cookies set."""
    email = unique_email("reg201")
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        response = await auth_client.post(
            REGISTER_URL,
            json={"email": email, "password": VALID_PASSWORD},
        )
    assert response.status_code == 201
    data = response.json()
    assert "user_id" in data
    assert data["email"] == email
    # Both cookies must be set
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_register_duplicate_email_409(auth_client):
    """Registering the same email twice returns 409."""
    email = unique_email("dup")
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        first = await auth_client.post(
            REGISTER_URL, json={"email": email, "password": VALID_PASSWORD}
        )
        assert first.status_code == 201
        response = await auth_client.post(
            REGISTER_URL, json={"email": email, "password": VALID_PASSWORD}
        )
    assert response.status_code == 409
    detail = response.json()["detail"].lower()
    assert "email" in detail or "зарегистрирован" in detail


@pytest.mark.asyncio
async def test_register_invalid_email_422(auth_client):
    """Non-email input returns 422 from Pydantic validation."""
    response = await auth_client.post(
        REGISTER_URL,
        json={"email": "not-an-email", "password": VALID_PASSWORD},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password_422(auth_client):
    """Password shorter than 8 characters returns 422."""
    response = await auth_client.post(
        REGISTER_URL,
        json={"email": unique_email("shortpwd"), "password": "short"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success_200(auth_client):
    """Happy-path login: returns 200, body has user_id + email, cookies set."""
    email = unique_email("login")
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        # Register first
        reg = await auth_client.post(
            REGISTER_URL, json={"email": email, "password": VALID_PASSWORD}
        )
        assert reg.status_code == 201
        # Then login
        response = await auth_client.post(
            LOGIN_URL, json={"email": email, "password": VALID_PASSWORD}
        )
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert data["email"] == email
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password_401(auth_client):
    """Wrong password returns 401 with no-enumeration message."""
    email = unique_email("wrongpwd")
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        reg = await auth_client.post(
            REGISTER_URL, json={"email": email, "password": VALID_PASSWORD}
        )
        assert reg.status_code == 201
        response = await auth_client.post(
            LOGIN_URL, json={"email": email, "password": "wrongpassword999"}
        )
    assert response.status_code == 401
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_login_unknown_email_401_same_message(auth_client):
    """Unknown email returns 401 with the same message as wrong password (no enumeration)."""
    email = unique_email("enumtest")
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        reg = await auth_client.post(
            REGISTER_URL, json={"email": email, "password": VALID_PASSWORD}
        )
        assert reg.status_code == 201
        response_wrong_pwd = await auth_client.post(
            LOGIN_URL, json={"email": email, "password": "wrongpassword999"}
        )
        response_unknown = await auth_client.post(
            LOGIN_URL,
            json={"email": unique_email("nonexistent"), "password": VALID_PASSWORD},
        )
    assert response_unknown.status_code == 401
    assert response_wrong_pwd.status_code == 401
    # Same detail message — no user enumeration
    assert response_unknown.json()["detail"] == response_wrong_pwd.json()["detail"]


@pytest.mark.asyncio
async def test_rate_limit_register_429(auth_client):
    """6th registration request within a minute returns 429 (slowapi)."""
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        responses = []
        for i in range(6):
            r = await auth_client.post(
                REGISTER_URL,
                json={"email": unique_email(f"rl{i}"), "password": VALID_PASSWORD},
            )
            responses.append(r)
    # First 5 succeed (201), 6th is rate-limited (429)
    assert responses[5].status_code == 429
