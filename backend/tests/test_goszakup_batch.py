"""Unit tests for goszakup_service.fetch_tenders_batch.

Covers DISC-02:
  - Single-page fetch returns items filtered by date
  - Authorization Bearer header is sent on every request
  - Items older than `since` are excluded (proper datetime comparison)
  - Empty API response returns []

Note: goszakup does NOT support 'offset' (confirmed 2026-07-22 — "Unknown argument
offset"). Offset-based pagination tests removed. Single page per poll.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import respx

from app.services.goszakup_service import GRAPHQL_URL, fetch_tenders_batch

# A fixed "since" datetime for all tests.
_SINCE = datetime(2026, 7, 10, 0, 0, 0, tzinfo=timezone.utc)
# A lastUpdateDate string clearly AFTER _SINCE (Almaty UTC+5: 2026-07-15 12:00 → UTC 07:00).
_RECENT_DATE = "2026-07-15 12:00:00"
# An older lastUpdateDate clearly BEFORE _SINCE.
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
        "Lots": [{"id": n * 10, "lotNumber": 1, "nameRu": f"Лот {n}", "nameKz": None, "amount": 500000}],
    }


def _gql_response(items: list[dict]) -> dict:
    """Wrap items in the goszakup GraphQL response envelope."""
    return {"data": {"TrdBuy": items}}


# ---------------------------------------------------------------------------
# Test 1: Single page — 30 items returned (< 50)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_batch_single_page_returns_30():
    """30 items returned — fetch_tenders_batch returns all 30."""
    items = [_make_tender(i) for i in range(30)]
    respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_gql_response(items))
    )

    result = await fetch_tenders_batch(since=_SINCE, limit=50)

    assert len(result) == 30, f"Expected 30 items, got {len(result)}"


# ---------------------------------------------------------------------------
# Test 2: Authorization Bearer header is sent
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

    await fetch_tenders_batch(since=_SINCE, limit=50)

    assert captured_auth, "No request was captured"
    auth_header = captured_auth[0]
    assert auth_header.startswith("Bearer "), (
        f"Authorization header must start with 'Bearer ', got: {auth_header!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: Items older than `since` are filtered out (datetime comparison)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_batch_filters_old_items():
    """Items with lastUpdateDate < since are excluded by client-side date filter.

    Uses proper datetime comparison via _parse_gz_date (Almaty UTC+5) — not
    broken lexicographic string comparison between space and T separators.
    """
    recent = [_make_tender(i, last_update=_RECENT_DATE) for i in range(5)]
    old = [_make_tender(i + 100, last_update=_OLD_DATE) for i in range(3)]
    all_items = recent + old

    respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_gql_response(all_items))
    )

    result = await fetch_tenders_batch(since=_SINCE, limit=50)

    assert len(result) == 5, f"Expected 5 (recent only), got {len(result)}"
    for item in result:
        assert item["lastUpdateDate"] == _RECENT_DATE


# ---------------------------------------------------------------------------
# Test 4: Empty API response → returns empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_batch_empty_response():
    """Empty TrdBuy array from API → fetch_tenders_batch returns []."""
    respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_gql_response([]))
    )

    result = await fetch_tenders_batch(since=_SINCE, limit=50)

    assert result == [], f"Expected [], got {result!r}"


# ---------------------------------------------------------------------------
# Test 5: GraphQL error response (goszakup returns 200 with errors, no data)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_batch_graphql_error_returns_empty():
    """When goszakup returns a GraphQL error (200 + errors, no data), returns [].

    This matches the actual goszakup behavior for invalid arguments — the API
    returns HTTP 200 with {"errors": [...]} and no "data" key.
    """
    error_body = {
        "errors": [{"message": "Unknown argument", "extensions": {"category": "graphql"}}],
        "extensions": {"pageInfo": {"limitPage": 0, "totalCount": 0, "hasNextPage": False}},
    }
    respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=error_body)
    )

    result = await fetch_tenders_batch(since=_SINCE, limit=50)

    assert result == [], f"Expected [] on GraphQL error, got {result!r}"
