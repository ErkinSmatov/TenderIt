"""Phase 5 — confirm flow integration tests (APPL-09 three branches).

Tests the three APPL-09 branches at the Redis-confirm + auto_submit level:
  Branch A: confirm="yes" → immediate submit proceeds → mark_submitted.
  Branch B: confirm="no"  → cancel → mark_error("Cancelled by user").
  Branch C: confirm=None/pending (no reply in 15 min) → fallback → proceeds to submit.

These test auto_submit_application directly with different confirm states in fakeredis.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
import respx
from httpx import Response

from app.workers.tasks.auto_submit import auto_submit_application

PORTAL_BASE = "https://v3bl.goszakup.gov.kz"


@pytest.fixture
async def fake_redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


def _make_app(app_id: int = 10, user_id: int = 5, tender_buy_id: int = 17163708):
    app = MagicMock()
    app.id = app_id
    app.user_id = user_id
    app.goszakup_application_id = 71931023
    app.goszakup_tender_buy_id = tender_buy_id
    app.status = "submitting"
    return app


def _make_ctx(redis_client, session, job_try: int = 1):
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return {
        "redis": redis_client,
        "db_session_factory": mock_factory,
        "job_try": job_try,
    }


def _make_session(app):
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = app
    session.execute = AsyncMock(return_value=mock_result)
    return session


# ---------------------------------------------------------------------------
# Branch A: confirm="yes" → immediate submit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_confirm_yes_immediate_submit(fake_redis):
    """APPL-09 Branch A: confirm='yes' → auto_submit proceeds → mark_submitted."""
    app = _make_app(app_id=10)
    session = _make_session(app)
    ctx = _make_ctx(fake_redis, session)

    # Set confirm=yes in Redis (simulates user clicking Да)
    await fake_redis.set(f"confirm:{app.id}", "yes")

    # Store goszakup session
    await fake_redis.setex(
        f"goszakup_session:{app.user_id}",
        3600,
        json.dumps(
            {
                "phpsessid": "sess",
                "csrf": "csrf",
                "application_id": 71931023,
                "tender_buy_id": 17163708,
            }
        ),
    )

    url = f"{PORTAL_BASE}/ru/application/ajax_public_application/17163708/71931023"
    respx.post(url).mock(return_value=Response(200, json={"status": "ok"}))

    with (
        patch(
            "app.workers.tasks.auto_submit.mark_submitted",
            new_callable=AsyncMock,
        ) as mock_submitted,
        patch(
            "app.workers.tasks.auto_submit.mark_error",
            new_callable=AsyncMock,
        ) as mock_error,
    ):
        await auto_submit_application(ctx, application_id=app.id)

    mock_submitted.assert_called_once()
    mock_error.assert_not_called()


# ---------------------------------------------------------------------------
# Branch B: confirm="no" → cancel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_no_cancels(fake_redis):
    """APPL-09 Branch B: confirm='no' → mark_error, no portal call."""
    app = _make_app(app_id=11)
    session = _make_session(app)
    ctx = _make_ctx(fake_redis, session)

    # User clicked Нет
    await fake_redis.set(f"confirm:{app.id}", "no")

    with (
        patch(
            "app.workers.tasks.auto_submit.mark_error",
            new_callable=AsyncMock,
        ) as mock_error,
        patch(
            "app.workers.tasks.auto_submit.mark_submitted",
            new_callable=AsyncMock,
        ) as mock_submitted,
    ):
        await auto_submit_application(ctx, application_id=app.id)

    mock_error.assert_called_once()
    assert "Cancelled" in str(mock_error.call_args)
    mock_submitted.assert_not_called()


# ---------------------------------------------------------------------------
# Branch C: confirm=None (expired / no reply) → fallback auto-submit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_confirm_expired_fallback_submit(fake_redis):
    """APPL-09 Branch C: confirm=None (TTL expired) → fallback → mark_submitted."""
    app = _make_app(app_id=12)
    session = _make_session(app)
    ctx = _make_ctx(fake_redis, session)

    # confirm:{id} is absent (expired after 15 min)
    # (nothing stored in fake_redis)

    await fake_redis.setex(
        f"goszakup_session:{app.user_id}",
        3600,
        json.dumps(
            {
                "phpsessid": "sess",
                "csrf": "csrf",
                "application_id": 71931023,
                "tender_buy_id": 17163708,
            }
        ),
    )

    url = f"{PORTAL_BASE}/ru/application/ajax_public_application/17163708/71931023"
    respx.post(url).mock(return_value=Response(200, json={"status": "ok"}))

    with (
        patch(
            "app.workers.tasks.auto_submit.mark_submitted",
            new_callable=AsyncMock,
        ) as mock_submitted,
        patch(
            "app.workers.tasks.auto_submit.mark_error",
            new_callable=AsyncMock,
        ) as mock_error,
    ):
        await auto_submit_application(ctx, application_id=app.id)

    # Fallback should submit despite no explicit confirm
    mock_submitted.assert_called_once()
    mock_error.assert_not_called()


# ---------------------------------------------------------------------------
# Branch C-pending: confirm="pending" → also proceeds to submit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_confirm_pending_still_submits(fake_redis):
    """APPL-09 Branch C (pending): confirm='pending' → auto_submit proceeds."""
    app = _make_app(app_id=13)
    session = _make_session(app)
    ctx = _make_ctx(fake_redis, session)

    # Still pending — user hasn't replied
    await fake_redis.set(f"confirm:{app.id}", "pending")

    await fake_redis.setex(
        f"goszakup_session:{app.user_id}",
        3600,
        json.dumps(
            {
                "phpsessid": "sess",
                "csrf": "csrf",
                "application_id": 71931023,
                "tender_buy_id": 17163708,
            }
        ),
    )

    url = f"{PORTAL_BASE}/ru/application/ajax_public_application/17163708/71931023"
    respx.post(url).mock(return_value=Response(200, json={"status": "ok"}))

    with patch(
        "app.workers.tasks.auto_submit.mark_submitted",
        new_callable=AsyncMock,
    ) as mock_submitted:
        await auto_submit_application(ctx, application_id=app.id)

    mock_submitted.assert_called_once()
