"""
Integration tests for /api/tenders/* and /api/watchlist routes.

HTTP to goszakup is mocked via respx. The real test database is used for
watchlist persistence (migration 0002 must be applied: `alembic upgrade head`).

All 6 tests GREEN — Wave 2 implementation complete.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
import respx
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.goszakup_service import GRAPHQL_URL

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_TRDBUY = {
    "numberAnno": "17163708-1",
    "nameRu": "Услуги тест тендер",
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
            "id": 1,
            "lotNumber": "LOT-001",
            "nameRu": "Лот 1",
            "nameKz": None,
            "descriptionRu": "Описание лота",
            "amount": 1000000,
            "refLotStatusId": 220,
        }
    ],
}

_SAMPLE_TRDBUY_2 = {
    **_SAMPLE_TRDBUY,
    "numberAnno": "99999999-1",
    "nameRu": "Второй тест тендер",
}


def _gz_ok(body: dict) -> httpx.Response:
    return httpx.Response(200, json={"data": {"TrdBuy": [body]}})


def _gz_404() -> httpx.Response:
    return httpx.Response(200, json={"data": {"TrdBuy": []}})


async def _register_and_login(prefix: str = "tendertest") -> AsyncClient:
    """Create a fresh AsyncClient authenticated as a new unique user."""
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        resp = await ac.post(
            "/api/auth/register",
            json={"email": email, "password": "SecurePass123"},
        )
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    return ac


@pytest_asyncio.fixture
async def authed():
    """Function-scoped authenticated client."""
    ac = await _register_and_login()
    yield ac
    await ac.aclose()


@pytest_asyncio.fixture
async def authed2():
    """Second independent authenticated client (for isolation tests)."""
    ac = await _register_and_login(prefix="tendertest2")
    yield ac
    await ac.aclose()


# ---------------------------------------------------------------------------
# Tender lookup tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_tender_found(authed):
    """GET /api/tenders/{n} returns 200 with full tender data when goszakup finds it."""
    respx.post(GRAPHQL_URL).mock(return_value=_gz_ok(_SAMPLE_TRDBUY))

    resp = await authed.get("/api/tenders/17163708-1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["number_anno"] == "17163708-1"
    assert body["name_ru"] == "Услуги тест тендер"
    assert body["status_name_ru"] == "Опубликовано (прием заявок)"
    assert body["lots_data"] is not None
    assert len(body["lots_data"]) == 1

    # 401 for unauthenticated request
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as anon:
        anon_resp = await anon.get("/api/tenders/17163708-1")
    assert anon_resp.status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_get_tender_not_found(authed):
    """GET /api/tenders/{n} returns 404 when goszakup returns an empty TrdBuy array."""
    respx.post(GRAPHQL_URL).mock(return_value=_gz_404())

    resp = await authed.get("/api/tenders/00000000-1")

    assert resp.status_code == 404
    assert "не найден" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Watchlist CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_add_to_watchlist(authed):
    """POST /api/watchlist adds a tender to the watchlist and returns 201."""
    respx.post(GRAPHQL_URL).mock(return_value=_gz_ok(_SAMPLE_TRDBUY))

    resp = await authed.post("/api/watchlist", json={"number_anno": "17163708-1"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["tender"]["number_anno"] == "17163708-1"
    assert body["notification_on"] is True
    assert "added_at" in body


@pytest.mark.asyncio
@respx.mock
async def test_add_watchlist_idempotent(authed):
    """POST /api/watchlist twice returns success both times; DB has exactly one row."""
    # goszakup is called only on first add (second is a cache hit)
    respx.post(GRAPHQL_URL).mock(return_value=_gz_ok(_SAMPLE_TRDBUY))

    r1 = await authed.post("/api/watchlist", json={"number_anno": "17163708-1"})
    assert r1.status_code in (200, 201)

    # Second add — tender is cached, respx route won't be called again necessarily
    # (but we allow it to be called if cache was not persisted cross-requests in test)
    respx.post(GRAPHQL_URL).mock(return_value=_gz_ok(_SAMPLE_TRDBUY))
    r2 = await authed.post("/api/watchlist", json={"number_anno": "17163708-1"})
    assert r2.status_code in (200, 201)

    # Verify watchlist has exactly one entry for this tender
    list_resp = await authed.get("/api/watchlist")
    assert list_resp.status_code == 200
    entries = list_resp.json()
    matching = [e for e in entries if e["tender"]["number_anno"] == "17163708-1"]
    assert len(matching) == 1, f"Expected 1 entry, found {len(matching)}"


@pytest.mark.asyncio
@respx.mock
async def test_remove_from_watchlist(authed):
    """DELETE /api/watchlist/{n} removes the entry; second DELETE returns 404."""
    respx.post(GRAPHQL_URL).mock(return_value=_gz_ok(_SAMPLE_TRDBUY))

    # Add first
    add_resp = await authed.post("/api/watchlist", json={"number_anno": "17163708-1"})
    assert add_resp.status_code in (200, 201)

    # Remove
    del_resp = await authed.delete("/api/watchlist/17163708-1")
    assert del_resp.status_code == 204

    # Second remove → 404 (already gone)
    del_resp2 = await authed.delete("/api/watchlist/17163708-1")
    assert del_resp2.status_code == 404


@pytest.mark.asyncio
@respx.mock
async def test_get_watchlist(authed, authed2):
    """GET /api/watchlist returns only the current user's entries (user isolation)."""
    # Add two tenders to user1's watchlist
    respx.post(GRAPHQL_URL).mock(return_value=_gz_ok(_SAMPLE_TRDBUY))
    r1 = await authed.post("/api/watchlist", json={"number_anno": "17163708-1"})
    assert r1.status_code in (200, 201)

    respx.post(GRAPHQL_URL).mock(return_value=_gz_ok(_SAMPLE_TRDBUY_2))
    r2 = await authed.post("/api/watchlist", json={"number_anno": "99999999-1"})
    assert r2.status_code in (200, 201)

    # user1 sees their 2 entries
    list_resp = await authed.get("/api/watchlist")
    assert list_resp.status_code == 200
    entries = list_resp.json()
    user1_numbers = {e["tender"]["number_anno"] for e in entries}
    assert "17163708-1" in user1_numbers
    assert "99999999-1" in user1_numbers

    # user2 sees none of user1's entries
    list_resp2 = await authed2.get("/api/watchlist")
    assert list_resp2.status_code == 200
    user2_entries = list_resp2.json()
    user2_numbers = {e["tender"]["number_anno"] for e in user2_entries}
    assert "17163708-1" not in user2_numbers
    assert "99999999-1" not in user2_numbers
