"""Phase 5 — auto_submit_application ARQ job tests.

Tests (Task 2):
  APPL-09a: Portal {"status":"ok"}   → application status becomes "submitted".
  APPL-09b: confirm:{id}="no"        → status "error" + public_application NOT called.
  APPL-09c: Portal {"status":"error"} on first try → arq.Retry raised.
  APPL-09d: All retries exhausted (job_try > len(BACKOFF_SECONDS)) → mark_error final.

Pattern:
  - fakeredis for confirm + goszakup_session state.
  - respx for mocking GoszakupPortalClient HTTP calls.
  - Mock DB session factory (no real DB needed for unit tests).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
import respx
from httpx import Response

from app.workers.tasks.auto_submit import BACKOFF_SECONDS, auto_submit_application

PORTAL_BASE = "https://v3bl.goszakup.gov.kz"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def fake_redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


def _make_app(app_id: int = 1, user_id: int = 10, tender_buy_id: int = 17163708):
    """Create a mock Application object."""
    app = MagicMock()
    app.id = app_id
    app.user_id = user_id
    app.goszakup_application_id = 71931023
    app.goszakup_tender_buy_id = tender_buy_id
    app.status = "submitting"
    return app


def _make_ctx(redis_client, session, job_try: int = 1):
    """Build a fake ARQ ctx with mock session factory."""
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return {
        "redis": redis_client,
        "db_session_factory": mock_factory,
        "job_try": job_try,
    }


def _make_session(app):
    """Create a mock DB session that returns the given app on execute."""
    from sqlalchemy.ext.asyncio import AsyncSession

    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = app
    session.execute = AsyncMock(return_value=mock_result)
    return session


# ---------------------------------------------------------------------------
# Test 1: Portal ok → mark_submitted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_auto_submit_ok_marks_submitted(fake_redis):
    """Portal returns {"status":"ok"} → application transitions to submitted."""
    app = _make_app(app_id=1, user_id=10, tender_buy_id=17163708)
    session = _make_session(app)
    ctx = _make_ctx(fake_redis, session, job_try=1)

    # Store goszakup session in Redis
    import json

    session_data = {
        "phpsessid": "test_sessid",
        "csrf": "test_csrf",
        "application_id": 71931023,
        "tender_buy_id": 17163708,
    }
    await fake_redis.setex(f"goszakup_session:{app.user_id}", 3600, json.dumps(session_data))

    # Mock goszakup portal → ok
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
# Test 2: confirm="no" → mark_error, portal NOT called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_auto_submit_confirm_no_cancels(fake_redis):
    """confirm:{id}="no" → mark_error("Cancelled by user") and portal NOT called."""
    app = _make_app(app_id=2, user_id=20)
    session = _make_session(app)
    ctx = _make_ctx(fake_redis, session)

    # Set confirm=no
    await fake_redis.set(f"confirm:{app.id}", "no")

    # Portal should NOT be called — use respx passthrough to catch unexpected calls
    respx.route(method="POST").mock(
        side_effect=AssertionError("Portal should not be called when confirm=no")
    )

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
    error_call_args = mock_error.call_args
    assert "Cancelled by user" in str(error_call_args)
    mock_submitted.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: Portal error on first try → Retry raised
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_auto_submit_portal_error_raises_retry(fake_redis):
    """Portal returns {"status":"error"} on first try → arq.Retry raised."""
    from arq import Retry

    app = _make_app(app_id=3, user_id=30, tender_buy_id=17163708)
    session = _make_session(app)
    ctx = _make_ctx(fake_redis, session, job_try=1)

    import json

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
    respx.post(url).mock(
        return_value=Response(200, json={"status": "error", "message": "Portal busy"})
    )

    with (
        patch(
            "app.workers.tasks.auto_submit.increment_retry",
            new_callable=AsyncMock,
        ),
        patch(
            "app.workers.tasks.auto_submit.mark_error",
            new_callable=AsyncMock,
        ) as mock_error,
    ):
        with pytest.raises(Retry):
            await auto_submit_application(ctx, application_id=app.id)

    # mark_error should NOT be called on first retry
    mock_error.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: Retries exhausted → mark_error (T-05-34)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_auto_submit_exhausted_retries_marks_error(fake_redis):
    """After all retries (job_try >= len(BACKOFF_SECONDS)) → mark_error final."""
    from arq import Retry

    app = _make_app(app_id=4, user_id=40, tender_buy_id=17163708)
    session = _make_session(app)
    # job_try = len(BACKOFF_SECONDS) = 7 → should NOT retry, should mark_error
    exhausted_try = len(BACKOFF_SECONDS)
    ctx = _make_ctx(fake_redis, session, job_try=exhausted_try)

    import json

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
    respx.post(url).mock(
        return_value=Response(
            200, json={"status": "error", "message": "Final failure"}
        )
    )

    with (
        patch(
            "app.workers.tasks.auto_submit.increment_retry",
            new_callable=AsyncMock,
        ),
        patch(
            "app.workers.tasks.auto_submit.mark_error",
            new_callable=AsyncMock,
        ) as mock_error,
    ):
        # Should NOT raise Retry — exhausted
        await auto_submit_application(ctx, application_id=app.id)

    mock_error.assert_called_once()


# ---------------------------------------------------------------------------
# Test 5: Missing goszakup session → Retry(defer=60)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_submit_missing_session_retries(fake_redis):
    """Missing goszakup session in Redis → Retry(defer=60)."""
    from arq import Retry

    app = _make_app(app_id=5, user_id=50)
    session = _make_session(app)
    ctx = _make_ctx(fake_redis, session, job_try=1)

    # No goszakup session stored in Redis

    with pytest.raises(Retry) as exc_info:
        await auto_submit_application(ctx, application_id=app.id)

    # Retry(defer=60) → defer_score=60000 ms in arq internals
    assert exc_info.value.defer_score == 60 * 1000
