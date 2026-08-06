"""Integration tests for poll_sk_kz_discovery ARQ cron task.

Covers SC-08-01 (sk.kz ARQ cron task):
  - After successful poll, sk_kz:last_polled_at Redis key is set to a valid ISO timestamp
  - When _upsert_tenders raises, sk_kz:last_polled_at is NOT updated (atomicity invariant)
  - First run (no Redis key): since is approximately 24 hours ago (DEFAULT_LOOKBACK_HOURS=24)
  - Empty response: Redis key IS updated (timestamp advanced) but run_matching is NOT enqueued

Uses fakeredis (in-memory Redis) and unittest.mock.patch to avoid live API/DB calls.
No actual PostgreSQL or zakup.sk.kz connections are made.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

from app.workers.tasks.poll_sk_kz_discovery import (
    DEFAULT_LOOKBACK_HOURS,
    LAST_POLLED_KEY,
    poll_sk_kz_discovery,
)

# ---------------------------------------------------------------------------
# Helpers
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


def _fake_tender_dict(n: int) -> dict:
    """Minimal sk.kz tender dict for mocking fetch_sk_tenders_page results."""
    return {
        "id": 1000000 + n,
        "nameRu": f"Тендер {n}",
        "advertStatus": "PUBLISHED",
        "sumTruNoNds": 100.0,
        "lastModifiedDate": "2026-08-05T10:00:00Z",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def fake_redis():
    """fakeredis client with enqueue_job mock (ARQ-compatible API)."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client.enqueue_job = AsyncMock()
    yield client
    await client.aclose()


# ---------------------------------------------------------------------------
# Patch targets
# ---------------------------------------------------------------------------

_PATCH_FETCH = "app.workers.tasks.poll_sk_kz_discovery.fetch_sk_tenders_page"
_PATCH_UPSERT = "app.workers.tasks.poll_sk_kz_discovery._upsert_tenders"


# ---------------------------------------------------------------------------
# Test 1: Successful poll → last_polled_at written to Redis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_sets_redis_key_after_success(fake_redis):
    """After a successful poll, sk_kz:last_polled_at is set to a valid ISO timestamp."""
    fake_tenders = [_fake_tender_dict(i) for i in range(3)]

    with (
        patch(_PATCH_FETCH, new_callable=AsyncMock, return_value=fake_tenders),
        patch(_PATCH_UPSERT, new_callable=AsyncMock, return_value=[1, 2, 3]),
    ):
        await poll_sk_kz_discovery(_make_ctx(fake_redis))

    ts_raw = await fake_redis.get(LAST_POLLED_KEY)
    assert ts_raw is not None, f"Expected {LAST_POLLED_KEY} to be set in Redis"

    dt = datetime.fromisoformat(ts_raw)
    assert dt.tzinfo is not None, "Timestamp must be timezone-aware"


# ---------------------------------------------------------------------------
# Test 2: _upsert_tenders raises → Redis key is NOT updated (atomicity invariant)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_does_not_update_redis_on_upsert_error(fake_redis):
    """When _upsert_tenders raises, sk_kz:last_polled_at stays at pre-existing value."""
    # Pre-populate key as if a previous poll ran
    await fake_redis.set(LAST_POLLED_KEY, "2026-08-01T00:00:00+00:00")

    with (
        patch(_PATCH_FETCH, new_callable=AsyncMock, return_value=[_fake_tender_dict(0)]),
        patch(_PATCH_UPSERT, new_callable=AsyncMock, side_effect=Exception("DB error")),
    ):
        with pytest.raises(Exception, match="DB error"):
            await poll_sk_kz_discovery(_make_ctx(fake_redis))

    ts_raw = await fake_redis.get(LAST_POLLED_KEY)
    assert ts_raw == "2026-08-01T00:00:00+00:00", (
        f"last_polled_at must not be changed on upsert failure, got: {ts_raw!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: First run (no Redis key) → since is ~24h ago
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_uses_24h_lookback_on_first_run(fake_redis):
    """First run (no Redis key): since should be approximately 24 hours ago."""
    since_used: list[datetime] = []

    async def capture_since(since, page=0, size=50):
        since_used.append(since)
        return []  # Empty → poll exits early but still updates Redis

    with patch(_PATCH_FETCH, side_effect=capture_since):
        await poll_sk_kz_discovery(_make_ctx(fake_redis))

    assert len(since_used) == 1, "fetch_sk_tenders_page was not called"

    expected_since = datetime.now(tz=timezone.utc) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)
    diff = abs((since_used[0] - expected_since).total_seconds())
    assert diff < 10, (
        f"Expected ~{DEFAULT_LOOKBACK_HOURS}h lookback but got diff={diff:.1f}s "
        f"(since_used={since_used[0]}, expected≈{expected_since})"
    )


# ---------------------------------------------------------------------------
# Test 4: Empty response → Redis key IS updated but enqueue_job NOT called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_empty_response_does_not_enqueue(fake_redis):
    """Empty response: Redis key IS updated but run_matching is NOT enqueued."""
    with patch(_PATCH_FETCH, new_callable=AsyncMock, return_value=[]):
        await poll_sk_kz_discovery(_make_ctx(fake_redis))

    ts_raw = await fake_redis.get(LAST_POLLED_KEY)
    assert ts_raw is not None, (
        "last_polled_at should be set even on empty response (marks 'we checked up to now')"
    )

    fake_redis.enqueue_job.assert_not_called()
