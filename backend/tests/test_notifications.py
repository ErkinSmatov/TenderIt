"""Notifications endpoint tests — Phase 6, NOTIF-04.

Tests (T-06-01 through T-06-06):
  T-06-01: POST /api/notifications/telegram/link-token → 200, deep_link with 43-char token
  T-06-02: POST /api/notifications/telegram/link-token without JWT → 401
  T-06-03: GET /api/notifications/status for new user → telegram_connected: false
  T-06-04: DELETE /api/notifications/telegram → 204; status reflects disconnected
  T-06-05: GET /api/notifications/status without JWT → 401
  T-06-06: DELETE /api/notifications/telegram without JWT → 401

Webhook /start handler tests (T-06-07 through T-06-10):
  T-06-07: /start TOKEN dispatched to _handle_start_command
  T-06-08: plain message does NOT dispatch to _handle_start_command
  T-06-09: plain /start (no token) dispatched but handler returns early
  T-06-10: expired token does not set telegram_chat_id (unit test on handler directly)

Security invariants tested:
  NOTIF-04: link-token flow — generate, status, disconnect
  T-06-01: secrets.token_urlsafe(32) produces 43-char URL-safe base64 token
  T-06-05: expired token clears link_token but NOT telegram_chat_id
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app

WEBHOOK_SECRET = "test-webhook-secret-notif"
CHAT_ID = 77777


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def authed_client():
    """HTTP client pre-authenticated via register — module-scoped to share cookies.

    Redis (store_refresh_token) is mocked so tests run without live Redis.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        email = f"notiftest_{uuid.uuid4().hex[:8]}@example.com"
        with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
            resp = await ac.post(
                "/api/auth/register",
                json={"email": email, "password": "SecurePass123"},
            )
        assert resp.status_code == 201, f"Register failed: {resp.text}"
        yield ac


@pytest_asyncio.fixture
async def webhook_notif_client():
    """HTTP test client with a mock arq_redis injected into app.state."""
    mock_arq_redis = AsyncMock()
    mock_arq_redis.enqueue_job = AsyncMock()
    app.state.arq_redis = mock_arq_redis
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    if hasattr(app.state, "arq_redis"):
        del app.state._state["arq_redis"]


@pytest.fixture
def override_webhook_secret(monkeypatch):
    """Inject test telegram_webhook_secret into settings."""
    from app.config import settings

    monkeypatch.setattr(settings, "telegram_webhook_secret", WEBHOOK_SECRET)
    return settings


# ---------------------------------------------------------------------------
# Helpers for webhook update payloads
# ---------------------------------------------------------------------------


def _start_message_update(chat_id: int, text: str) -> dict:
    """Build a Telegram Update JSON for a message update."""
    return {
        "update_id": 200000001,
        "message": {
            "message_id": 99,
            "from": {"id": chat_id, "first_name": "TestUser", "is_bot": False},
            "chat": {"id": chat_id, "type": "private"},
            "date": int(time.time()),
            "text": text,
        },
    }


# ---------------------------------------------------------------------------
# Task 2 tests: endpoint behavior (T-06-01 through T-06-06)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_link_token(authed_client, monkeypatch):
    """POST /api/notifications/telegram/link-token → 200 with valid deep_link."""
    from app.config import settings

    monkeypatch.setattr(settings, "telegram_bot_username", "tenderitbot")

    resp = await authed_client.post("/api/notifications/telegram/link-token")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert "deep_link" in body, f"Missing deep_link in response: {body}"
    assert body["deep_link"].startswith(
        "https://t.me/tenderitbot?start="
    ), f"Unexpected deep_link: {body['deep_link']}"

    token = body["deep_link"].split("?start=")[1]
    assert len(token) == 43, (
        f"Token length {len(token)} != 43 — secrets.token_urlsafe(32) must produce 43 chars"
    )


@pytest.mark.asyncio
async def test_link_token_unauthenticated():
    """POST without JWT cookie → 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/notifications/telegram/link-token")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


@pytest.mark.asyncio
async def test_get_status_not_connected(authed_client):
    """GET /api/notifications/status for fresh user → telegram_connected: false."""
    resp = await authed_client.get("/api/notifications/status")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["telegram_connected"] is False, f"Expected False, got {body['telegram_connected']}"
    assert body["telegram_chat_id"] is None, f"Expected None, got {body['telegram_chat_id']}"


@pytest.mark.asyncio
async def test_disconnect(authed_client, monkeypatch):
    """DELETE /api/notifications/telegram → 204; subsequent GET shows disconnected."""
    from app.config import settings

    monkeypatch.setattr(settings, "telegram_bot_username", "tenderitbot")

    # Generate a link token first (so there's something to clear)
    resp = await authed_client.post("/api/notifications/telegram/link-token")
    assert resp.status_code == 200, resp.text

    # Disconnect
    resp = await authed_client.delete("/api/notifications/telegram")
    assert resp.status_code == 204, f"Expected 204, got {resp.status_code}: {resp.text}"

    # Status should show disconnected
    resp = await authed_client.get("/api/notifications/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["telegram_connected"] is False


@pytest.mark.asyncio
async def test_status_unauthenticated():
    """GET /api/notifications/status without JWT → 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/notifications/status")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


@pytest.mark.asyncio
async def test_disconnect_unauthenticated():
    """DELETE /api/notifications/telegram without JWT → 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.delete("/api/notifications/telegram")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Task 3 tests: /start webhook handler (T-06-07 through T-06-10)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_start_links_telegram(webhook_notif_client, override_webhook_secret):
    """POST webhook with /start TOKEN dispatches to _handle_start_command."""
    body = _start_message_update(chat_id=CHAT_ID, text="/start validtoken123")

    with patch(
        "app.routers.telegram_webhook._handle_start_command",
        new_callable=AsyncMock,
    ) as mock_handler:
        resp = await webhook_notif_client.post(
            "/api/telegram/webhook",
            json=body,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_webhook_plain_message_no_dispatch(webhook_notif_client, override_webhook_secret):
    """POST webhook with plain 'Hello' text does NOT call _handle_start_command."""
    body = _start_message_update(chat_id=CHAT_ID, text="Hello")

    with patch(
        "app.routers.telegram_webhook._handle_start_command",
        new_callable=AsyncMock,
    ) as mock_handler:
        resp = await webhook_notif_client.post(
            "/api/telegram/webhook",
            json=body,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    # Webhook pre-filters: only /start messages are dispatched to _handle_start_command.
    # A plain "Hello" message must NOT reach the handler (WR-02).
    mock_handler.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_plain_start_no_dispatch(webhook_notif_client, override_webhook_secret):
    """POST webhook with '/start' (no token) — handler is called but returns early."""
    body = _start_message_update(chat_id=CHAT_ID, text="/start")

    with patch(
        "app.routers.telegram_webhook._handle_start_command",
        new_callable=AsyncMock,
    ) as mock_handler:
        resp = await webhook_notif_client.post(
            "/api/telegram/webhook",
            json=body,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_expired_token_does_not_set_chat_id():
    """T-06-10 (T-06-05): expired link token must NOT set telegram_chat_id.

    Tests _handle_start_command directly using a mock db session and user.
    Expired token → chat_id remains None.
    """
    from app.routers.telegram_webhook import _handle_start_command

    # Build a mock message with /start token text
    mock_message = MagicMock()
    mock_message.text = "/start expiredtoken123"
    mock_message.from_user = MagicMock()
    mock_message.from_user.id = CHAT_ID

    # User with expired token
    mock_user = MagicMock()
    mock_user.telegram_link_token = "expiredtoken123"
    mock_user.telegram_link_token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    mock_user.telegram_chat_id = None

    # Mock DB session
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    # Mock bot to capture send_message calls
    mock_bot = AsyncMock()
    mock_bot_ctx = AsyncMock()
    mock_bot_ctx.__aenter__ = AsyncMock(return_value=mock_bot)
    mock_bot_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.routers.telegram_webhook.telegram.Bot", return_value=mock_bot_ctx):
        await _handle_start_command(mock_message, mock_db)

    # telegram_chat_id must NOT be set — expired token
    assert mock_user.telegram_chat_id is None, (
        "telegram_chat_id must remain None for expired token (T-06-05)"
    )
    # Token fields must be cleared even on expiry
    assert mock_user.telegram_link_token is None, (
        "telegram_link_token must be cleared on expiry"
    )
    # Bot must have sent an expiry message
    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args
    assert "устарела" in str(call_kwargs).lower() or "устарела" in str(
        mock_bot.send_message.call_args
    ), "Bot must send expiry message containing 'устарела'"
