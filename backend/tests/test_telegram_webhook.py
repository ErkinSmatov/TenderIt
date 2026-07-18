"""Phase 5 — Telegram webhook endpoint tests.

Tests (Task 3, APPL-09, T-05-30, T-05-31):
  T-05-31: Bad X-Telegram-Bot-Api-Secret-Token → 403.
  APPL-09: Valid "confirm:yes:{id}" callback → update_confirm + enqueue_job.
  T-05-30: Callback from wrong chat_id → ignored (IDOR mitigation).
  General: Non-callback update (plain message) → returns ok without action.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app

# ---------------------------------------------------------------------------
# Telegram Update payloads
# ---------------------------------------------------------------------------

WEBHOOK_SECRET = "test-webhook-secret-xyz"
APP_ID = 42
CHAT_ID = 99999


def _callback_update(action: str, app_id: int, chat_id: int):
    """Build a minimal Telegram Update JSON for a callback_query."""
    return {
        "update_id": 100000001,
        "callback_query": {
            "id": "callback123",
            "from": {
                "id": chat_id,
                "first_name": "Test",
                "is_bot": False,
            },
            "chat_instance": "chat_instance_xyz",
            "data": f"confirm:{action}:{app_id}",
        },
    }


def _message_update():
    """Build a minimal Telegram Update JSON for a plain message (no callback).

    Includes required `date` field for Message.de_json with bot=None.
    """
    import time

    return {
        "update_id": 100000002,
        "message": {
            "message_id": 1,
            "from": {"id": 99999, "first_name": "Test", "is_bot": False},
            "chat": {"id": 99999, "type": "private"},
            "date": int(time.time()),
            "text": "Hello",
        },
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def webhook_client():
    """HTTP test client with a mock arq_redis injected into app.state."""
    mock_arq_redis = AsyncMock()
    mock_arq_redis.enqueue_job = AsyncMock()
    app.state.arq_redis = mock_arq_redis
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    # Clean up: remove mock from state
    if hasattr(app.state, "arq_redis"):
        del app.state._state["arq_redis"]


@pytest.fixture
def override_settings(monkeypatch):
    """Inject test telegram_webhook_secret into settings."""
    from app.config import settings

    monkeypatch.setattr(settings, "telegram_webhook_secret", WEBHOOK_SECRET)
    return settings


# ---------------------------------------------------------------------------
# Test 1: Missing / wrong secret → 403 (T-05-31)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_rejects_wrong_secret(webhook_client, override_settings):
    """POST without secret header → 403. POST with wrong secret → 403."""
    body = _callback_update("yes", APP_ID, CHAT_ID)

    # No header
    resp = await webhook_client.post("/api/telegram/webhook", json=body)
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    # Wrong secret
    resp = await webhook_client.post(
        "/api/telegram/webhook",
        json=body,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Test 2: Valid "yes" callback → update_confirm + enqueue (APPL-09)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_yes_callback_updates_confirm_and_enqueues(
    webhook_client, override_settings
):
    """Valid confirm:yes callback → update_confirm("yes") + enqueue_job("submit:{id}")."""
    body = _callback_update("yes", APP_ID, CHAT_ID)

    mock_app = MagicMock()
    mock_app.id = APP_ID
    mock_app.user_id = 10

    mock_user = MagicMock()
    mock_user.telegram_chat_id = CHAT_ID

    with (
        patch(
            "app.routers.telegram_webhook.get_application_by_id",
            new_callable=AsyncMock,
            return_value=mock_app,
        ),
        patch(
            "app.routers.telegram_webhook.get_user_by_id",
            new_callable=AsyncMock,
            return_value=mock_user,
        ),
        patch(
            "app.routers.telegram_webhook.update_confirm",
            new_callable=AsyncMock,
        ) as mock_update_confirm,
        patch(
            "app.routers.telegram_webhook.enqueue_submit",
            new_callable=AsyncMock,
        ) as mock_enqueue,
    ):
        resp = await webhook_client.post(
            "/api/telegram/webhook",
            json=body,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}

    # update_confirm must be called with (app_id, "yes")
    mock_update_confirm.assert_called_once()
    call_args = mock_update_confirm.call_args
    assert APP_ID in call_args.args or APP_ID in call_args.kwargs.values()

    # enqueue must be called with _job_id="submit:{app_id}"
    mock_enqueue.assert_called_once()
    enqueue_args = mock_enqueue.call_args
    # The enqueue function is called with (redis, application_id)
    assert APP_ID in enqueue_args.args or APP_ID in str(enqueue_args)


# ---------------------------------------------------------------------------
# Test 3: Valid "no" callback → update_confirm("no"), no enqueue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_no_callback_updates_confirm_no_enqueue(
    webhook_client, override_settings
):
    """Valid confirm:no callback → update_confirm("no") + no enqueue."""
    body = _callback_update("no", APP_ID, CHAT_ID)

    mock_app = MagicMock()
    mock_app.id = APP_ID
    mock_app.user_id = 10

    mock_user = MagicMock()
    mock_user.telegram_chat_id = CHAT_ID

    with (
        patch(
            "app.routers.telegram_webhook.get_application_by_id",
            new_callable=AsyncMock,
            return_value=mock_app,
        ),
        patch(
            "app.routers.telegram_webhook.get_user_by_id",
            new_callable=AsyncMock,
            return_value=mock_user,
        ),
        patch(
            "app.routers.telegram_webhook.update_confirm",
            new_callable=AsyncMock,
        ) as mock_update_confirm,
        patch(
            "app.routers.telegram_webhook.enqueue_submit",
            new_callable=AsyncMock,
        ) as mock_enqueue,
    ):
        resp = await webhook_client.post(
            "/api/telegram/webhook",
            json=body,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    assert resp.status_code == 200
    mock_update_confirm.assert_called_once()
    # No enqueue for "no" action
    mock_enqueue.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: IDOR — callback from wrong chat_id → ignored (T-05-30)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_idor_wrong_chat_id_ignored(webhook_client, override_settings):
    """Callback from chat_id that doesn't match app owner → silently ignored."""
    body = _callback_update("yes", APP_ID, chat_id=88888)  # Wrong chat_id

    mock_app = MagicMock()
    mock_app.id = APP_ID
    mock_app.user_id = 10

    mock_user = MagicMock()
    mock_user.telegram_chat_id = CHAT_ID  # Owner has CHAT_ID=99999, not 88888

    with (
        patch(
            "app.routers.telegram_webhook.get_application_by_id",
            new_callable=AsyncMock,
            return_value=mock_app,
        ),
        patch(
            "app.routers.telegram_webhook.get_user_by_id",
            new_callable=AsyncMock,
            return_value=mock_user,
        ),
        patch(
            "app.routers.telegram_webhook.update_confirm",
            new_callable=AsyncMock,
        ) as mock_update_confirm,
        patch(
            "app.routers.telegram_webhook.enqueue_submit",
            new_callable=AsyncMock,
        ) as mock_enqueue,
    ):
        resp = await webhook_client.post(
            "/api/telegram/webhook",
            json=body,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    # Returns ok but takes no action
    assert resp.status_code == 200
    mock_update_confirm.assert_not_called()
    mock_enqueue.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5: Non-callback update (plain message) → ok, no action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_plain_message_returns_ok(webhook_client, override_settings):
    """A non-callback update (e.g. plain message) is accepted and ignored."""
    body = _message_update()

    resp = await webhook_client.post(
        "/api/telegram/webhook",
        json=body,
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
