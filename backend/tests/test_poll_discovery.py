"""Integration tests for poll_goszakup_discovery ARQ cron task.

Covers DISC-02:
  - Redis key discovery:last_polled_at is written after a successful poll
  - On fetch failure (HTTPStatusError 500), last_polled_at is NOT updated (atomicity)
  - On first run (no Redis key), since defaults to ~7 days ago

Uses fakeredis (in-memory Redis) and mocks fetch_tenders_batch + _upsert_tenders
to avoid live API calls and real DB connections.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import httpx
import pytest

from app.workers.tasks.poll_goszakup_discovery import (
    LAST_POLLED_KEY,
    poll_goszakup_discovery,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_ctx(redis_client) -> dict:
    """Build a minimal fake ARQ ctx with fakeredis and a mock session factory."""
    mock_session = AsyncMock()
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return {
        "redis": redis_client,
        "db_session_factory": mock_factory,
    }


def _make_fake_tender(number_anno: str = "1234567-1") -> dict:
    """Minimal TrdBuy dict for mocking fetch_tenders_batch results."""
    return {
        "id": 99,
        "numberAnno": number_anno,
        "nameRu": "Тестовый тендер",
        "nameKz": None,
        "totalSum": 500000,
        "customerBin": "123456789012",
        "customerNameRu": "ТОО Тест",
        "customerNameKz": None,
        "refBuyStatusId": 220,
        "startDate": "2026-07-10 00:00:00",
        "endDate": "2026-07-20 00:00:00",
        "publishDate": "2026-07-09 00:00:00",
        "lastUpdateDate": "2026-07-15 12:00:00",
        "Lots": [],
    }


@pytest.fixture
async def fake_redis():
    """fakeredis client with enqueue_job mock (ARQ-compatible API)."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client.enqueue_job = AsyncMock()
    yield client
    await client.aclose()


# ---------------------------------------------------------------------------
# Test 1: Successful poll → last_polled_at written to Redis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_writes_last_polled_at_after_success(fake_redis):
    """After a successful poll, discovery:last_polled_at is set to a valid ISO timestamp."""
    fake_tenders = [_make_fake_tender("1234567-1"), _make_fake_tender("2345678-1"), _make_fake_tender("3456789-1")]

    ctx = _make_ctx(fake_redis)

    before_poll = datetime.now(tz=timezone.utc)

    with (
        patch(
            "app.workers.tasks.poll_goszakup_discovery.fetch_tenders_batch",
            new_callable=AsyncMock,
            # Return 3 items on first call, empty on second (stop pagination)
            side_effect=[fake_tenders, []],
        ),
        patch(
            "app.workers.tasks.poll_goszakup_discovery._upsert_tenders",
            new_callable=AsyncMock,
            return_value=[1, 2, 3],
        ),
    ):
        await poll_goszakup_discovery(ctx)

    # Verify last_polled_at was written
    ts_raw = await fake_redis.get(LAST_POLLED_KEY)
    assert ts_raw is not None, f"Expected {LAST_POLLED_KEY} to be set in Redis"

    # Verify it is a valid ISO 8601 datetime string
    ts_parsed = datetime.fromisoformat(ts_raw)
    assert ts_parsed >= before_poll, (
        f"last_polled_at ({ts_parsed}) should be after the poll start ({before_poll})"
    )


# ---------------------------------------------------------------------------
# Test 2: fetch_tenders_batch raises HTTPStatusError 500 → no last_polled_at update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_does_not_write_last_polled_at_on_fetch_error(fake_redis):
    """When fetch_tenders_batch raises HTTPStatusError 500, last_polled_at stays unset."""
    ctx = _make_ctx(fake_redis)

    # Simulate a server-side error from goszakup
    http_error = httpx.HTTPStatusError(
        "Internal Server Error",
        request=httpx.Request("POST", "https://ows.goszakup.gov.kz/v3/graphql"),
        response=httpx.Response(500),
    )

    with (
        patch(
            "app.workers.tasks.poll_goszakup_discovery.fetch_tenders_batch",
            new_callable=AsyncMock,
            side_effect=http_error,
        ),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await poll_goszakup_discovery(ctx)

    # last_polled_at must NOT be written when fetch fails
    ts_raw = await fake_redis.get(LAST_POLLED_KEY)
    assert ts_raw is None, (
        f"last_polled_at must NOT be set when fetch_tenders_batch fails, got: {ts_raw!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: First run (no key in Redis) → since defaults to ~7 days ago
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_defaults_to_7_days_ago_on_first_run(fake_redis):
    """On first run (no Redis key), since argument passed to fetch_tenders_batch
    is approximately 7 days before now."""
    ctx = _make_ctx(fake_redis)

    captured_since: list[datetime] = []

    async def capture_fetch(since: datetime, limit: int = 50, offset: int = 0):
        captured_since.append(since)
        return []  # Empty response → poll exits early

    with patch(
        "app.workers.tasks.poll_goszakup_discovery.fetch_tenders_batch",
        side_effect=capture_fetch,
    ):
        await poll_goszakup_discovery(ctx)

    assert captured_since, "fetch_tenders_batch was not called"

    since_used = captured_since[0]
    now = datetime.now(tz=timezone.utc)
    expected_since = now - timedelta(days=7)

    # Allow ±10 seconds tolerance for test execution time
    diff = abs((since_used - expected_since).total_seconds())
    assert diff < 10, (
        f"First-run since should be ~7 days ago. "
        f"Got: {since_used}, expected ~{expected_since} (diff={diff:.1f}s)"
    )


# ---------------------------------------------------------------------------
# Test 4: run_matching job is enqueued with list of upserted tender IDs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_enqueues_run_matching_with_upserted_ids(fake_redis):
    """After successful upsert, run_matching is enqueued with the list of IDs."""
    fake_tenders = [_make_fake_tender("1234567-1")]
    ctx = _make_ctx(fake_redis)
    upserted_ids = [42, 43, 44]

    with (
        patch(
            "app.workers.tasks.poll_goszakup_discovery.fetch_tenders_batch",
            new_callable=AsyncMock,
            side_effect=[fake_tenders, []],
        ),
        patch(
            "app.workers.tasks.poll_goszakup_discovery._upsert_tenders",
            new_callable=AsyncMock,
            return_value=upserted_ids,
        ),
    ):
        await poll_goszakup_discovery(ctx)

    fake_redis.enqueue_job.assert_called_once_with("run_matching", upserted_ids)


# ---------------------------------------------------------------------------
# Test 5: No new tenders → last_polled_at still written (timestamp advanced)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_advances_timestamp_even_when_no_new_tenders(fake_redis):
    """When fetch_tenders_batch returns empty, last_polled_at is still updated."""
    ctx = _make_ctx(fake_redis)

    before_poll = datetime.now(tz=timezone.utc)

    with patch(
        "app.workers.tasks.poll_goszakup_discovery.fetch_tenders_batch",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await poll_goszakup_discovery(ctx)

    ts_raw = await fake_redis.get(LAST_POLLED_KEY)
    assert ts_raw is not None, "last_polled_at must be set even when no tenders fetched"
    ts_parsed = datetime.fromisoformat(ts_raw)
    assert ts_parsed >= before_poll
