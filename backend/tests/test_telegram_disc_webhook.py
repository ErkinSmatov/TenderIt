"""Phase 7 — Telegram webhook disc:* callback handler tests.

Tests (DISC-05, T-07-01, T-07-02, T-07-05):
  1. test_disc_prefix_accepted: disc:participate:* passes guard → enters disc: branch
  2. test_disc_participate_idor: wrong chat_id → silently ignored, no Application created
  3. test_disc_skip_idor: wrong chat_id → silently ignored, match status unchanged
  4. test_disc_participate_creates_draft: correct chat_id → Application created, match=participating
  5. test_disc_skip_sets_skipped: correct chat_id → match.status='skipped'
  6. test_secret_token_required: no secret → 403 (T-05-31 still applies to disc:*)

Pattern: mirrors test_telegram_webhook.py — uses full HTTP client with mocked helpers.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WEBHOOK_SECRET = "test-webhook-secret-xyz"
MATCH_ID = 77
MATCH_OWNER_CHAT_ID = 111111
OTHER_CHAT_ID = 222222
USER_ID = 5
TENDER_ID = 99


# ---------------------------------------------------------------------------
# Telegram Update payloads
# ---------------------------------------------------------------------------


def _disc_update(action: str, match_id: int, chat_id: int) -> dict:
    """Build a minimal Telegram Update JSON for a disc:* callback_query."""
    return {
        "update_id": 200000001,
        "callback_query": {
            "id": "disc_callback_123",
            "from": {
                "id": chat_id,
                "first_name": "Test",
                "is_bot": False,
            },
            "chat_instance": "chat_instance_disc_abc",
            "data": f"disc:{action}:{match_id}",
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
    if hasattr(app.state, "arq_redis"):
        del app.state._state["arq_redis"]


@pytest.fixture
def override_settings(monkeypatch):
    """Inject test telegram_webhook_secret and bot_token into settings."""
    from app.config import settings

    monkeypatch.setattr(settings, "telegram_webhook_secret", WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "telegram_bot_token", "test:bot_token")
    return settings


# ---------------------------------------------------------------------------
# Mock builders
# ---------------------------------------------------------------------------


def _mock_match(
    match_id: int = MATCH_ID,
    user_id: int = USER_ID,
    tender_id: int = TENDER_ID,
    status: str = "matched",
) -> MagicMock:
    """Build a minimal TenderMatch MagicMock."""
    m = MagicMock()
    m.id = match_id
    m.user_id = user_id
    m.tender_id = tender_id
    m.status = status
    m.decided_at = None
    return m


def _mock_owner(chat_id: int = MATCH_OWNER_CHAT_ID) -> MagicMock:
    """Build a minimal User MagicMock with a telegram_chat_id."""
    u = MagicMock()
    u.telegram_chat_id = chat_id
    return u


def _patch_bot():
    """Return a context manager that patches telegram.Bot to avoid real API calls."""
    mock_bot_instance = AsyncMock()
    mock_bot_cls = MagicMock()
    mock_bot_cls.return_value.__aenter__ = AsyncMock(return_value=mock_bot_instance)
    mock_bot_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return patch("telegram.Bot", return_value=mock_bot_cls.return_value), mock_bot_cls


# ---------------------------------------------------------------------------
# Test 1: disc:* prefix passes the guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disc_prefix_accepted(webhook_client, override_settings):
    """disc:participate:1 passes the guard and enters the disc: branch (Research pitfall 2).

    Even if the match is not found, the handler returns {"ok": True} — not a 403
    or an early guard return. This verifies the guard change from != 'confirm'
    to not in ('confirm', 'disc').
    """
    body = _disc_update("participate", MATCH_ID, MATCH_OWNER_CHAT_ID)

    with patch(
        "app.routers.telegram_webhook.get_tender_match_by_id",
        new_callable=AsyncMock,
        return_value=None,  # match not found → handler returns {"ok": True} with warning
    ):
        resp = await webhook_client.post(
            "/api/telegram/webhook",
            json=body,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    # Guard passed (not 403); disc: branch reached; match-not-found path returns ok
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# ---------------------------------------------------------------------------
# Test 2: IDOR — participate from wrong chat_id → ignored
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disc_participate_idor(webhook_client, override_settings):
    """disc:participate from wrong chat_id → silently ignored, Application NOT created (T-07-01)."""
    body = _disc_update("participate", MATCH_ID, OTHER_CHAT_ID)  # wrong chat_id

    mock_match = _mock_match()
    mock_owner = _mock_owner(chat_id=MATCH_OWNER_CHAT_ID)  # owner's chat_id != OTHER_CHAT_ID

    with (
        patch(
            "app.routers.telegram_webhook.get_tender_match_by_id",
            new_callable=AsyncMock,
            return_value=mock_match,
        ),
        patch(
            "app.routers.telegram_webhook.get_user_by_id",
            new_callable=AsyncMock,
            return_value=mock_owner,
        ),
        patch(
            "app.routers.telegram_webhook.create_discovery_draft",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        resp = await webhook_client.post(
            "/api/telegram/webhook",
            json=body,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_create.assert_not_called()  # Application must NOT be created
    assert mock_match.status == "matched"  # match status must remain unchanged


# ---------------------------------------------------------------------------
# Test 3: IDOR — skip from wrong chat_id → ignored
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disc_skip_idor(webhook_client, override_settings):
    """disc:skip from wrong chat_id → silently ignored, match status unchanged (T-07-02)."""
    body = _disc_update("skip", MATCH_ID, OTHER_CHAT_ID)

    mock_match = _mock_match()
    mock_owner = _mock_owner(chat_id=MATCH_OWNER_CHAT_ID)

    with (
        patch(
            "app.routers.telegram_webhook.get_tender_match_by_id",
            new_callable=AsyncMock,
            return_value=mock_match,
        ),
        patch(
            "app.routers.telegram_webhook.get_user_by_id",
            new_callable=AsyncMock,
            return_value=mock_owner,
        ),
    ):
        resp = await webhook_client.post(
            "/api/telegram/webhook",
            json=body,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert mock_match.status == "matched"  # unchanged


# ---------------------------------------------------------------------------
# Test 4: disc:participate happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disc_participate_creates_draft(webhook_client, override_settings):
    """disc:participate from match owner → Application created (status=draft), match=participating."""
    body = _disc_update("participate", MATCH_ID, MATCH_OWNER_CHAT_ID)

    mock_match = _mock_match()
    mock_owner = _mock_owner(chat_id=MATCH_OWNER_CHAT_ID)

    mock_app = MagicMock()
    mock_app.id = 999
    mock_app.status = "draft"

    with (
        patch(
            "app.routers.telegram_webhook.get_tender_match_by_id",
            new_callable=AsyncMock,
            return_value=mock_match,
        ),
        patch(
            "app.routers.telegram_webhook.get_user_by_id",
            new_callable=AsyncMock,
            return_value=mock_owner,
        ),
        patch(
            "app.routers.telegram_webhook.create_discovery_draft",
            new_callable=AsyncMock,
            return_value=mock_app,
        ) as mock_create,
        patch("telegram.Bot") as mock_bot_cls,
    ):
        # Mock telegram.Bot context manager to avoid real API calls
        mock_bot_instance = AsyncMock()
        mock_bot_cls.return_value.__aenter__ = AsyncMock(return_value=mock_bot_instance)
        mock_bot_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await webhook_client.post(
            "/api/telegram/webhook",
            json=body,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # create_discovery_draft must be called with (db, user_id, tender_id)
    mock_create.assert_called_once()
    call_args = mock_create.call_args
    # args: (db, user_id, tender_id) — positional
    assert call_args.args[1] == USER_ID
    assert call_args.args[2] == TENDER_ID

    # match.status must be updated to "participating"
    assert mock_match.status == "participating"


# ---------------------------------------------------------------------------
# Test 5: disc:skip happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disc_skip_sets_skipped(webhook_client, override_settings):
    """disc:skip from match owner → match.status='skipped'."""
    body = _disc_update("skip", MATCH_ID, MATCH_OWNER_CHAT_ID)

    mock_match = _mock_match()
    mock_owner = _mock_owner(chat_id=MATCH_OWNER_CHAT_ID)

    with (
        patch(
            "app.routers.telegram_webhook.get_tender_match_by_id",
            new_callable=AsyncMock,
            return_value=mock_match,
        ),
        patch(
            "app.routers.telegram_webhook.get_user_by_id",
            new_callable=AsyncMock,
            return_value=mock_owner,
        ),
        patch("telegram.Bot") as mock_bot_cls,
    ):
        mock_bot_instance = AsyncMock()
        mock_bot_cls.return_value.__aenter__ = AsyncMock(return_value=mock_bot_instance)
        mock_bot_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await webhook_client.post(
            "/api/telegram/webhook",
            json=body,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert mock_match.status == "skipped"


# ---------------------------------------------------------------------------
# Test 6: Secret token required (T-05-31 still applies to disc:*)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_secret_token_required(webhook_client, override_settings):
    """Sending disc:* without X-Telegram-Bot-Api-Secret-Token → 403 (T-05-31)."""
    body = _disc_update("participate", MATCH_ID, MATCH_OWNER_CHAT_ID)

    resp = await webhook_client.post("/api/telegram/webhook", json=body)
    assert resp.status_code == 403
