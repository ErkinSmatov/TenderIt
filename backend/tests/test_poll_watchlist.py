"""Phase 5 — poll_watchlist_tenders ARQ cron job tests.

Tests:
  APPL-07: ARQ cron detects status_id 220 and enqueues auto_submit with _job_id
  APPL-08: Telegram notification triggered on status 220 (if telegram_chat_id set)
  APPL-08-fallback: No telegram_chat_id → still enqueues submit (no crash)
  Poll-skip: Non-220 tender → no enqueue, no confirm set
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

from app.workers.tasks.poll_watchlist import poll_watchlist_tenders


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_mock_app(app_id: int = 42, user_id: int = 7, tender_id: int = 100):
    app = MagicMock()
    app.id = app_id
    app.user_id = user_id
    app.tender_id = tender_id
    return app


def _make_mock_tender(number_anno: str = "17163708-1"):
    t = MagicMock()
    t.number_anno = number_anno
    return t


def _make_mock_user(telegram_chat_id=99999):
    u = MagicMock()
    u.telegram_chat_id = telegram_chat_id
    return u


def _make_ctx(redis_client, session):
    """Build a fake ARQ ctx dict with a mock session factory and the given redis."""
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return {
        "redis": redis_client,
        "db_session_factory": mock_factory,
    }


@pytest.fixture
async def fake_redis():
    """fakeredis client with decode_responses + enqueue_job mock."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client.enqueue_job = AsyncMock()
    yield client
    await client.aclose()


# ---------------------------------------------------------------------------
# Test 1: Status 220 → set_confirm_pending + enqueue with correct job_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_enqueues_on_status_220(fake_redis):
    """Status 220 → confirm:pending set + enqueue_job with _defer_by + _job_id."""
    app = _make_mock_app(app_id=42)
    tender = _make_mock_tender("17163708-1")
    user = _make_mock_user(telegram_chat_id=99999)

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(
        side_effect=lambda cls, pk: user if "User" in cls.__name__ else tender
    )
    # UserWatchlist query returns None (notification_on defaults to True)
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    ctx = _make_ctx(fake_redis, mock_session)

    with (
        patch(
            "app.workers.tasks.poll_watchlist.list_waiting_applications",
            return_value=[app],
        ),
        patch(
            "app.workers.tasks.poll_watchlist.fetch_tender_by_number_anno",
            return_value={"refBuyStatusId": 220, "numberAnno": "17163708-1"},
        ),
        patch(
            "app.workers.tasks.poll_watchlist.mark_submitting",
            new_callable=AsyncMock,
            return_value=app,
        ) as mock_mark,
        patch(
            "app.workers.tasks.poll_watchlist.send_tender_notification",
            new_callable=AsyncMock,
        ) as mock_notify,
    ):
        await poll_watchlist_tenders(ctx)

    # confirm:{app_id} must be set to "pending" in Redis
    confirm_value = await fake_redis.get(f"confirm:{app.id}")
    assert confirm_value == "pending", f"Expected 'pending', got {confirm_value!r}"

    # enqueue_job must be called with _defer_by + stable _job_id
    fake_redis.enqueue_job.assert_called_once_with(
        "auto_submit_application",
        app.id,
        _defer_by=timedelta(minutes=15),
        _job_id=f"submit:{app.id}",
    )

    # mark_submitting must be called
    mock_mark.assert_called_once()

    # Telegram notification must be sent (user has chat_id)
    mock_notify.assert_called_once()


# ---------------------------------------------------------------------------
# Test 2: No telegram_chat_id → no crash, submit still enqueued
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_no_crash_when_no_telegram_chat_id(fake_redis):
    """No telegram_chat_id → fallback submit still enqueued, no notification sent."""
    app = _make_mock_app(app_id=55)
    tender = _make_mock_tender("99999999-1")
    user = _make_mock_user(telegram_chat_id=None)

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(
        side_effect=lambda cls, pk: user if "User" in cls.__name__ else tender
    )
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    ctx = _make_ctx(fake_redis, mock_session)

    with (
        patch(
            "app.workers.tasks.poll_watchlist.list_waiting_applications",
            return_value=[app],
        ),
        patch(
            "app.workers.tasks.poll_watchlist.fetch_tender_by_number_anno",
            return_value={"refBuyStatusId": 220},
        ),
        patch(
            "app.workers.tasks.poll_watchlist.mark_submitting",
            new_callable=AsyncMock,
            return_value=app,
        ),
        patch(
            "app.workers.tasks.poll_watchlist.send_tender_notification",
            new_callable=AsyncMock,
        ) as mock_notify,
    ):
        await poll_watchlist_tenders(ctx)

    # Submit still enqueued despite no telegram
    fake_redis.enqueue_job.assert_called_once_with(
        "auto_submit_application",
        app.id,
        _defer_by=timedelta(minutes=15),
        _job_id=f"submit:{app.id}",
    )

    # Notification must NOT be sent
    mock_notify.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: Non-220 tender → no confirm, no enqueue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_skips_non_220_tender(fake_redis):
    """Non-220 tender → confirm NOT set, enqueue NOT called."""
    app = _make_mock_app(app_id=77)
    tender = _make_mock_tender("88888888-1")
    user = _make_mock_user()

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(
        side_effect=lambda cls, pk: user if "User" in cls.__name__ else tender
    )
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    ctx = _make_ctx(fake_redis, mock_session)

    with (
        patch(
            "app.workers.tasks.poll_watchlist.list_waiting_applications",
            return_value=[app],
        ),
        patch(
            "app.workers.tasks.poll_watchlist.fetch_tender_by_number_anno",
            # Status 210 = not yet open
            return_value={"refBuyStatusId": 210},
        ),
        patch(
            "app.workers.tasks.poll_watchlist.mark_submitting",
            new_callable=AsyncMock,
        ) as mock_mark,
        patch(
            "app.workers.tasks.poll_watchlist.send_tender_notification",
            new_callable=AsyncMock,
        ) as mock_notify,
    ):
        await poll_watchlist_tenders(ctx)

    # No confirm set
    confirm_value = await fake_redis.get(f"confirm:{app.id}")
    assert confirm_value is None

    # No enqueue
    fake_redis.enqueue_job.assert_not_called()

    # No transition
    mock_mark.assert_not_called()
    mock_notify.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: No waiting applications → worker is a no-op
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_noop_when_no_waiting_apps(fake_redis):
    """Empty waiting list → no DB/Redis/HTTP calls beyond the initial query."""
    mock_session = AsyncMock()
    ctx = _make_ctx(fake_redis, mock_session)

    with (
        patch(
            "app.workers.tasks.poll_watchlist.list_waiting_applications",
            return_value=[],
        ),
        patch(
            "app.workers.tasks.poll_watchlist.fetch_tender_by_number_anno",
            new_callable=AsyncMock,
        ) as mock_fetch,
    ):
        await poll_watchlist_tenders(ctx)

    mock_fetch.assert_not_called()
    fake_redis.enqueue_job.assert_not_called()
