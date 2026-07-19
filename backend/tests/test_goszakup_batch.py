"""Unit tests for goszakup_service.fetch_tenders_batch.

Covers DISC-02:
  - Pagination stop condition: returns < limit → caller should stop
  - Correct offset parameter forwarded to goszakup GraphQL API
  - Authorization Bearer header is sent on every request

All tests use respx to mock POST to GRAPHQL_URL — no live API calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from app.services.goszakup_service import GRAPHQL_URL, fetch_tenders_batch

# A fixed "since" datetime for all tests.
_SINCE = datetime(2026, 7, 10, 0, 0, 0, tzinfo=timezone.utc)
# A lastUpdateDate string that is clearly AFTER _SINCE (so items pass the filter).
_RECENT_DATE = "2026-07-15 12:00:00"
# An older lastUpdateDate that is BEFORE _SINCE (so items are filtered out).
_OLD_DATE = "2026-07-01 00:00:00"


def _make_tender(n: int, last_update: str = _RECENT_DATE) -> dict:
    """Generate a minimal TrdBuy dict for test purposes."""
    return {
        "id": n,
        "numberAnno": f"1000000{n}-1",
        "nameRu": f"Тендер {n}",
        "nameKz": None,
        "totalSum": 1000000,
        "customerBin": "123456789012",
        "customerNameRu": "ТОО Тест",
        "customerNameKz": None,
        "refBuyStatusId": 220,
        "startDate": "2026-07-10 00:00:00",
        "endDate": "2026-07-20 00:00:00",
        "publishDate": "2026-07-09 00:00:00",
        "lastUpdateDate": last_update,
        "Lots": [{"id": n * 10, "lotNumber": 1, "nameRu": f"Лот {n}", "nameKz": None, "amount": 500000, "refEnstruCode": "01.13.30.000"}],
    }


def _gql_response(items: list[dict]) -> dict:
    """Wrap items in the goszakup GraphQL response envelope."""
    return {"data": {"TrdBuy": items}}


# ---------------------------------------------------------------------------
# Test 1: Single page — mock returns 30 items (< 50) → function returns those 30
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_batch_single_page_returns_30():
    """30 items returned (< limit of 50) → fetch_tenders_batch returns all 30."""
    items = [_make_tender(i) for i in range(30)]
    respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_gql_response(items))
    )

    result = await fetch_tenders_batch(since=_SINCE, limit=50, offset=0)

    assert len(result) == 30, f"Expected 30 items, got {len(result)}"
    # Verify caller would stop: len(result) < limit
    assert len(result) < 50, "30 < 50 → caller should stop paginating"


# ---------------------------------------------------------------------------
# Test 2: Correct offset parameter forwarded to goszakup API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_batch_sends_correct_offset():
    """fetch_tenders_batch(offset=50) must send variables.offset=50 to the API."""
    items = [_make_tender(i) for i in range(10)]

    captured_body: dict = {}

    def capture_and_respond(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(200, json=_gql_response(items))

    respx.post(GRAPHQL_URL).mock(side_effect=capture_and_respond)

    result = await fetch_tenders_batch(since=_SINCE, limit=50, offset=50)

    assert len(result) == 10
    variables = captured_body.get("variables", {})
    assert variables.get("offset") == 50, (
        f"Expected variables.offset=50, got {variables.get('offset')!r}"
    )
    assert variables.get("limit") == 50, (
        f"Expected variables.limit=50, got {variables.get('limit')!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: Authorization Bearer header is sent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_batch_sends_bearer_token():
    """fetch_tenders_batch must include Authorization: Bearer <token> header."""
    items = [_make_tender(i) for i in range(5)]

    captured_auth: list[str] = []

    def capture_and_respond(request: httpx.Request) -> httpx.Response:
        captured_auth.append(request.headers.get("Authorization", ""))
        return httpx.Response(200, json=_gql_response(items))

    respx.post(GRAPHQL_URL).mock(side_effect=capture_and_respond)

    await fetch_tenders_batch(since=_SINCE, limit=50, offset=0)

    assert captured_auth, "No request was captured"
    auth_header = captured_auth[0]
    assert auth_header.startswith("Bearer "), (
        f"Authorization header must start with 'Bearer ', got: {auth_header!r}"
    )
    # The token value is non-empty (from settings; may be empty string in test env)
    # We only assert the prefix — not the value (CLAUDE.md: never log/assert tokens)


# ---------------------------------------------------------------------------
# Test 4: Items older than `since` are filtered out by client-side stop condition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_batch_filters_old_items():
    """Items with lastUpdateDate < since are excluded by client-side filter."""
    recent = [_make_tender(i, last_update=_RECENT_DATE) for i in range(5)]
    old = [_make_tender(i + 100, last_update=_OLD_DATE) for i in range(3)]
    all_items = recent + old

    respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_gql_response(all_items))
    )

    result = await fetch_tenders_batch(since=_SINCE, limit=50, offset=0)

    # Only the 5 recent items should be returned
    assert len(result) == 5, f"Expected 5 (recent only), got {len(result)}"
    for item in result:
        assert item["lastUpdateDate"] == _RECENT_DATE


# ---------------------------------------------------------------------------
# Test 5: Empty API response → returns empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_batch_empty_response():
    """Empty TrdBuy array from API → fetch_tenders_batch returns []."""
    respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_gql_response([]))
    )

    result = await fetch_tenders_batch(since=_SINCE, limit=50, offset=0)

    assert result == [], f"Expected [], got {result!r}"
