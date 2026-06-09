"""
Integration tests for POST /api/auth/register and POST /api/auth/login.

Tests use the session-scoped AsyncClient fixture from conftest.py.
Redis calls in register/login are mocked via monkeypatching store_refresh_token
so tests run without a live Redis instance.
"""
import pytest
from unittest.mock import AsyncMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"

VALID_EMAIL = "testuser@example.com"
VALID_PASSWORD = "securepassword123"


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_success_201(client):
    """Happy-path registration: returns 201, body has user_id + email, cookies set."""
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        response = await client.post(
            REGISTER_URL,
            json={"email": "newuser_201@example.com", "password": VALID_PASSWORD},
        )
    assert response.status_code == 201
    data = response.json()
    assert "user_id" in data
    assert data["email"] == "newuser_201@example.com"
    # Both cookies must be set
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_register_duplicate_email_409(client):
    """Registering the same email twice returns 409."""
    email = "duplicate_test@example.com"
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        await client.post(REGISTER_URL, json={"email": email, "password": VALID_PASSWORD})
        response = await client.post(
            REGISTER_URL, json={"email": email, "password": VALID_PASSWORD}
        )
    assert response.status_code == 409
    assert "email" in response.json()["detail"].lower() or "зарегистрирован" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_invalid_email_422(client):
    """Non-email input returns 422 from Pydantic validation."""
    response = await client.post(
        REGISTER_URL,
        json={"email": "not-an-email", "password": VALID_PASSWORD},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password_422(client):
    """Password shorter than 8 characters returns 422."""
    response = await client.post(
        REGISTER_URL,
        json={"email": "shortpwd@example.com", "password": "short"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success_200(client):
    """Happy-path login: returns 200, body has user_id + email, cookies set."""
    email = "loginuser@example.com"
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        # Register first
        await client.post(REGISTER_URL, json={"email": email, "password": VALID_PASSWORD})
        # Then login
        response = await client.post(
            LOGIN_URL, json={"email": email, "password": VALID_PASSWORD}
        )
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert data["email"] == email
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password_401(client):
    """Wrong password returns 401 with no-enumeration message."""
    email = "wrongpwd@example.com"
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        await client.post(REGISTER_URL, json={"email": email, "password": VALID_PASSWORD})
        response = await client.post(
            LOGIN_URL, json={"email": email, "password": "wrongpassword999"}
        )
    assert response.status_code == 401
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_login_unknown_email_401_same_message(client):
    """Unknown email returns 401 with the same message as wrong password (no enumeration)."""
    response_unknown = await client.post(
        LOGIN_URL,
        json={"email": "nonexistent@example.com", "password": VALID_PASSWORD},
    )
    email = "enumtest@example.com"
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        await client.post(REGISTER_URL, json={"email": email, "password": VALID_PASSWORD})
        response_wrong_pwd = await client.post(
            LOGIN_URL, json={"email": email, "password": "wrongpassword999"}
        )
    assert response_unknown.status_code == 401
    assert response_wrong_pwd.status_code == 401
    # Same detail message — no user enumeration
    assert response_unknown.json()["detail"] == response_wrong_pwd.json()["detail"]


@pytest.mark.asyncio
async def test_rate_limit_register_429(client):
    """6th registration request within a minute returns 429 (slowapi)."""
    base_email = "ratelimit_register_{i}@example.com"
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        responses = []
        for i in range(6):
            r = await client.post(
                REGISTER_URL,
                json={"email": base_email.format(i=i), "password": VALID_PASSWORD},
            )
            responses.append(r)
    # First 5 are allowed (201 or 409), 6th is 429
    assert responses[5].status_code == 429
