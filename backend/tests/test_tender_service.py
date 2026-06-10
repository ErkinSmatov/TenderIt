"""
Unit tests for goszakup_service and tender_service.

HTTP layer is mocked via respx (no live API calls).
DB layer is mocked via unittest.mock.AsyncMock (no live PostgreSQL needed).

All 5 tests are GREEN (not skipped) — Wave 1 implementation is complete.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

from app.models.tender import Tender
from app.services.goszakup_service import GRAPHQL_URL, fetch_tender_by_number_anno
from app.services.tender_service import CACHE_TTL_MINUTES, get_or_fetch_tender

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_TRDBUY = {
    "numberAnno": "17163708-1",
    "nameRu": "Test tender",
    "nameKz": None,
    "totalSum": 1000000,
    "countLots": 1,
    "customerBin": "000000000000",
    "customerNameRu": None,
    "customerNameKz": None,
    "refBuyStatusId": 220,
    "RefBuyStatus": {
        "id": 220,
        "nameRu": "Опубликовано (прием заявок)",
        "nameKz": "Жарияланды",
        "code": "PublishedOrderTaking",
    },
    "startDate": "2026-06-10 17:57:53",
    "endDate": "2026-06-12 17:57:53",
    "publishDate": "2026-06-10 17:57:53",
    "lastUpdateDate": "2026-06-10 17:54:54",
    "Lots": [
        {
            "id": 42212976,
            "lotNumber": "81638850-ОИ2",
            "nameRu": "Test lot",
            "nameKz": None,
            "descriptionRu": "Test",
            "amount": 1000000,
            "refLotStatusId": 220,
        }
    ],
}


def _mock_api_200(body: dict) -> httpx.Response:
    return httpx.Response(200, json={"data": {"TrdBuy": [body]}})


def _mock_api_404() -> httpx.Response:
    return httpx.Response(200, json={"data": {"TrdBuy": []}})


# ---------------------------------------------------------------------------
# Service unit tests (respx mocks HTTP, AsyncMock mocks DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_tender_found():
    """fetch_tender_by_number_anno returns a dict when the API finds the tender."""
    respx.post(GRAPHQL_URL).mock(return_value=_mock_api_200(_SAMPLE_TRDBUY))

    result = await fetch_tender_by_number_anno("17163708-1")

    assert result is not None
    assert result["numberAnno"] == "17163708-1"
    assert result["refBuyStatusId"] == 220


@pytest.mark.asyncio
@respx.mock
async def test_fetch_tender_not_found():
    """fetch_tender_by_number_anno returns None when TrdBuy array is empty (404-equivalent)."""
    respx.post(GRAPHQL_URL).mock(return_value=_mock_api_404())

    result = await fetch_tender_by_number_anno("99999999-1")

    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_cache_hit_skips_api():
    """A cached Tender with cached_at within 30 min is returned without hitting the API.

    respx.mock with no routes registered means any HTTP call raises — confirming
    that get_or_fetch_tender did NOT call the API when the cache is fresh.
    """
    fresh_cached_at = datetime.now(tz=timezone.utc)
    fresh_tender = Tender(
        id=1,
        number_anno="17163708-1",
        name_ru="Cached tender",
        status_id=220,
        cached_at=fresh_cached_at,
        created_at=fresh_cached_at,
    )

    mock_db = AsyncMock()
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = fresh_tender
    mock_db.execute.return_value = select_result

    result = await get_or_fetch_tender(mock_db, "17163708-1")

    assert result is fresh_tender
    # Exactly one DB execute (the SELECT) — no upsert
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
@respx.mock
async def test_cache_stale_refetches():
    """A stale Tender (cached_at > 30 min) triggers a fresh API call and upserts."""
    stale_cached_at = datetime.now(tz=timezone.utc) - timedelta(minutes=CACHE_TTL_MINUTES + 1)
    stale_tender = Tender(
        id=1,
        number_anno="17163708-1",
        name_ru="Old name",
        status_id=220,
        cached_at=stale_cached_at,
        created_at=stale_cached_at,
    )
    fresh_upserted = Tender(
        id=1,
        number_anno="17163708-1",
        name_ru="Fresh name",
        status_id=220,
        cached_at=datetime.now(tz=timezone.utc),
        created_at=stale_cached_at,
    )

    # First execute → SELECT (returns stale)
    # Second execute → pg_insert upsert (returns fresh)
    mock_db = AsyncMock()
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = stale_tender
    upsert_result = MagicMock()
    upsert_result.scalar_one.return_value = fresh_upserted
    mock_db.execute.side_effect = [select_result, upsert_result]

    respx.post(GRAPHQL_URL).mock(return_value=_mock_api_200(_SAMPLE_TRDBUY))

    result = await get_or_fetch_tender(mock_db, "17163708-1")

    assert result is fresh_upserted
    # Two DB executes: SELECT + upsert
    assert mock_db.execute.call_count == 2
    # API was called (one HTTP request)
    assert respx.calls.call_count == 1


@pytest.mark.asyncio
async def test_tender_response_schema():
    """Tender ORM model has all required fields for the TenderResponse schema (Wave 2)."""
    now = datetime.now(tz=timezone.utc)
    tender = Tender(
        number_anno="17163708-1",
        name_ru="Услуги по тех. обслуживанию",
        name_kz=None,
        total_sum=24180000,
        customer_name_ru=None,
        customer_name_kz=None,
        status_id=220,
        status_name_ru="Опубликовано (прием заявок)",
        start_date=now,
        end_date=now + timedelta(days=2),
        publish_date=now,
        lots_data=[{"id": 1, "nameRu": "Lot 1", "amount": 24180000}],
        raw_data={"numberAnno": "17163708-1"},
        cached_at=now,
        created_at=now,
    )

    # All fields required by the Wave 2 TenderResponse schema must exist
    required_fields = [
        "number_anno",
        "name_ru",
        "total_sum",
        "customer_name_ru",
        "status_id",
        "status_name_ru",
        "start_date",
        "end_date",
        "lots_data",
        "cached_at",
    ]
    for field in required_fields:
        assert hasattr(tender, field), f"Tender model missing field: {field}"

    assert tender.number_anno == "17163708-1"
    assert tender.status_id == 220
    assert tender.lots_data is not None
    assert isinstance(tender.lots_data, list)
