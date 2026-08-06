"""Unit tests for sk_kz_service.fetch_sk_tenders_page.

Covers SC-08-01 (zakup.sk.kz REST client):
  - Recent items (lastModifiedDate >= since) are returned
  - Old items (lastModifiedDate < since) are filtered out client-side
  - Empty array response returns []
  - No Authorization header is sent (public endpoint — assert header == "NONE")
  - HTTP 500 response raises httpx.HTTPStatusError (retryable — tenacity reraises)

No live HTTP calls are made — respx.mock intercepts all requests.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import respx

from app.services.sk_kz_service import fetch_sk_tenders_page

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# A fixed "since" datetime for all tests
_SINCE = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)

# A lastModifiedDate string clearly AFTER _SINCE (ISO 8601 with Z suffix)
_RECENT_DATE = "2026-08-05T10:00:00Z"

# A lastModifiedDate string clearly BEFORE _SINCE
_OLD_DATE = "2026-07-25T00:00:00Z"

# The exact filter endpoint URL (confirmed from HAR 2026-08-06)
_FILTER_URL = "https://zakup.sk.kz/eprocsearch/api/external/4dv3rts/filter"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_sk_tender(n: int, modified: str = _RECENT_DATE) -> dict:
    """Minimal sk.kz filter response item for test purposes."""
    return {
        "id": 1000000 + n,
        "number": str(1000000 + n),
        "nameRu": f"Тендер {n}",
        "nameKk": None,
        "tenderType": "OTP",
        "sumTruNoNds": 1000000.0,
        "acceptanceBeginDateTime": "2026-08-06T05:00:00Z",
        "acceptanceEndDateTime": "2026-08-17T05:00:00Z",
        "advertStatus": "PUBLISHED",
        "lastModifiedDate": modified,
    }


# ---------------------------------------------------------------------------
# Test 1: Recent items are returned
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_page_returns_recent_items():
    """fetch_sk_tenders_page returns all items when all are recent (>= since)."""
    items = [_make_sk_tender(i) for i in range(3)]
    respx.post(_FILTER_URL).mock(return_value=httpx.Response(200, json=items))

    result = await fetch_sk_tenders_page(since=_SINCE)

    assert len(result) == 3
    assert result[0]["id"] == 1000000


# ---------------------------------------------------------------------------
# Test 2: Old items are filtered out
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_page_filters_old_items():
    """Items with lastModifiedDate < since are excluded by client-side date filter."""
    items = [
        _make_sk_tender(0, _RECENT_DATE),  # newer — should be kept
        _make_sk_tender(1, _OLD_DATE),      # older  — should be filtered out
    ]
    respx.post(_FILTER_URL).mock(return_value=httpx.Response(200, json=items))

    result = await fetch_sk_tenders_page(since=_SINCE)

    assert len(result) == 1, f"Expected 1 recent item, got {len(result)}"
    assert result[0]["id"] == 1000000


# ---------------------------------------------------------------------------
# Test 3: Empty array response returns []
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_page_empty_response():
    """Empty array from sk.kz filter endpoint → returns []."""
    respx.post(_FILTER_URL).mock(return_value=httpx.Response(200, json=[]))

    result = await fetch_sk_tenders_page(since=_SINCE)

    assert result == [], f"Expected [], got {result!r}"


# ---------------------------------------------------------------------------
# Test 4: No Authorization header is sent (public endpoint)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_page_sends_no_auth_header():
    """sk.kz filter is public — no Authorization header should be sent."""
    captured: list[str] = []

    def capture(request: httpx.Request) -> httpx.Response:
        captured.append(request.headers.get("Authorization", "NONE"))
        return httpx.Response(200, json=[])

    respx.post(_FILTER_URL).mock(side_effect=capture)

    await fetch_sk_tenders_page(since=_SINCE)

    assert len(captured) >= 1, "No request was captured by respx"
    assert captured[0] == "NONE", (
        f"Should not send auth header to public sk.kz endpoint, got: {captured[0]!r}"
    )


# ---------------------------------------------------------------------------
# Test 5: HTTP 500 raises HTTPStatusError (tenacity reraises after 3 attempts)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_page_500_raises():
    """HTTP 500 from sk.kz → tenacity retries 3 times, then reraises HTTPStatusError."""
    respx.post(_FILTER_URL).mock(return_value=httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        await fetch_sk_tenders_page(since=_SINCE)
