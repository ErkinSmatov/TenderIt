"""Phase 5 — Application CRUD endpoint tests.

Covers:
  APPL-01: POST /api/applications — create draft application (status="draft", user_id from JWT)
  APPL-05: GET /api/applications  — list only current user's applications
  T-05-01: GET /api/applications/{id} — returns 404 (not 403) for another user's app (IDOR)
  T-05-02: POST /api/applications — user_id from JWT, never body

Test strategy:
  - respx.mock for goszakup GraphQL (tender lookup)
  - Real test DB (Postgres) for persistence — same as test_tenders.py pattern
  - Two authenticated clients (authed / authed2) for isolation tests
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import app.db as db_module
import httpx
import pytest
import pytest_asyncio
import respx
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models.tender import Tender
from app.services.goszakup_service import GRAPHQL_URL

# ---------------------------------------------------------------------------
# Sample goszakup API data
# ---------------------------------------------------------------------------

_SAMPLE_TRDBUY = {
    "id": 17269797,
    "numberAnno": "17269797-1",
    "nameRu": "Тест тендер для заявок",
    "nameKz": None,
    "totalSum": 500000,
    "countLots": 1,
    "customerBin": "000000000001",
    "customerNameRu": "Заказчик тест",
    "customerNameKz": None,
    "refBuyStatusId": 220,
    "RefBuyStatus": {
        "id": 220,
        "nameRu": "Опубликовано (прием заявок)",
        "nameKz": None,
        "code": "PublishedOrderTaking",
    },
    "startDate": "2026-07-01 10:00:00",
    "endDate": "2026-07-15 10:00:00",
    "publishDate": "2026-07-01 09:00:00",
    "lastUpdateDate": "2026-07-01 09:00:00",
    "Lots": [
        {
            "id": 42460233,
            "lotNumber": "1",
            "nameRu": "Лот тест",
            "nameKz": None,
            "descriptionRu": "Описание лота теста",
            "amount": 500000,
            "refLotStatusId": 220,
        }
    ],
}


def _gz_ok(body: dict) -> httpx.Response:
    return httpx.Response(200, json={"data": {"TrdBuy": [body]}})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


async def _register_and_login(prefix: str = "apptest") -> AsyncClient:
    """Create a fresh AsyncClient authenticated as a new unique user."""
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        resp = await ac.post(
            "/api/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    return ac


@pytest_asyncio.fixture
async def authed():
    """Function-scoped authenticated client (user prefix: apptest)."""
    ac = await _register_and_login(prefix="apptest")
    yield ac
    await ac.aclose()


@pytest_asyncio.fixture
async def authed2():
    """Second independent authenticated client (user prefix: apptest2) for IDOR tests."""
    ac = await _register_and_login(prefix="apptest2")
    yield ac
    await ac.aclose()


async def _get_or_create_tender_id(number_anno: str, gz_data: dict) -> int:
    """Helper: ensure tender is in DB (via GET /api/... with goszakup mock) and return its DB id."""
    async with db_module.AsyncSessionLocal() as session:
        result = await session.execute(
            select(Tender).where(Tender.number_anno == number_anno)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing.id

    # Not in DB — insert via API using a temporary client
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        email = f"tendersetup_{uuid.uuid4().hex[:8]}@example.com"
        with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
            await ac.post(
                "/api/auth/register",
                json={"email": email, "password": "SecurePass123!"},
            )
        with respx.mock:
            respx.post(GRAPHQL_URL).mock(return_value=_gz_ok(gz_data))
            await ac.get(f"/api/tenders/{number_anno}")

    async with db_module.AsyncSessionLocal() as session:
        result = await session.execute(
            select(Tender).where(Tender.number_anno == number_anno)
        )
        tender = result.scalar_one()
        return tender.id


# ---------------------------------------------------------------------------
# Sample lots data
# ---------------------------------------------------------------------------

_SAMPLE_LOTS = [
    {
        "lot_id": 42460233,
        "unit_price": "100.00",
        "quantity": 5,
        "total_price": "500.00",
    }
]


# ---------------------------------------------------------------------------
# POST /api/applications tests (APPL-01, T-05-02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_create_application_returns_201(authed):
    """POST /api/applications returns 201 with status='draft' (APPL-01)."""
    # Ensure tender exists in DB
    respx.post(GRAPHQL_URL).mock(return_value=_gz_ok(_SAMPLE_TRDBUY))
    await authed.get("/api/tenders/17269797-1")

    tender_id = await _get_or_create_tender_id("17269797-1", _SAMPLE_TRDBUY)

    resp = await authed.post(
        "/api/applications",
        json={
            "tender_id": tender_id,
            "lots_data": _SAMPLE_LOTS,
            "document_ids": [],
        },
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["tender_id"] == tender_id
    assert "id" in body


@pytest.mark.asyncio
@respx.mock
async def test_create_application_user_id_from_jwt(authed, authed2):
    """user_id in created application must come from JWT, not body (T-05-02)."""
    respx.post(GRAPHQL_URL).mock(return_value=_gz_ok(_SAMPLE_TRDBUY))
    await authed.get("/api/tenders/17269797-1")

    tender_id = await _get_or_create_tender_id("17269797-1", _SAMPLE_TRDBUY)

    # User 1 creates application
    resp1 = await authed.post(
        "/api/applications",
        json={"tender_id": tender_id, "lots_data": _SAMPLE_LOTS},
    )
    assert resp1.status_code == 201
    app_id = resp1.json()["id"]

    # User 2 cannot see user 1's application (IDOR)
    resp2 = await authed2.get(f"/api/applications/{app_id}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_create_application_requires_auth():
    """POST /api/applications returns 401 for unauthenticated request."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
        resp = await anon.post(
            "/api/applications",
            json={"tender_id": 1, "lots_data": _SAMPLE_LOTS},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_create_application_empty_lots_rejected(authed):
    """POST /api/applications with empty lots_data returns 422 (input validation T-05-05)."""
    respx.post(GRAPHQL_URL).mock(return_value=_gz_ok(_SAMPLE_TRDBUY))
    await authed.get("/api/tenders/17269797-1")

    tender_id = await _get_or_create_tender_id("17269797-1", _SAMPLE_TRDBUY)

    resp = await authed.post(
        "/api/applications",
        json={"tender_id": tender_id, "lots_data": []},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/applications tests (APPL-05)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_list_applications_returns_only_own(authed, authed2):
    """GET /api/applications returns only current user's applications (APPL-05)."""
    respx.post(GRAPHQL_URL).mock(return_value=_gz_ok(_SAMPLE_TRDBUY))
    await authed.get("/api/tenders/17269797-1")

    tender_id = await _get_or_create_tender_id("17269797-1", _SAMPLE_TRDBUY)

    # User 1 creates an application
    create_resp = await authed.post(
        "/api/applications",
        json={"tender_id": tender_id, "lots_data": _SAMPLE_LOTS},
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    # User 1 sees their application
    list_resp1 = await authed.get("/api/applications")
    assert list_resp1.status_code == 200
    ids1 = [a["id"] for a in list_resp1.json()]
    assert app_id in ids1

    # User 2 does NOT see user 1's application (isolation)
    list_resp2 = await authed2.get("/api/applications")
    assert list_resp2.status_code == 200
    ids2 = [a["id"] for a in list_resp2.json()]
    assert app_id not in ids2


@pytest.mark.asyncio
async def test_list_applications_requires_auth():
    """GET /api/applications returns 401 for unauthenticated request."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
        resp = await anon.get("/api/applications")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/applications/{id} — IDOR tests (T-05-01)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_application_idor_returns_404(authed, authed2):
    """GET /api/applications/{id} returns 404 (not 403) for another user's application (T-05-01)."""
    respx.post(GRAPHQL_URL).mock(return_value=_gz_ok(_SAMPLE_TRDBUY))
    await authed.get("/api/tenders/17269797-1")

    tender_id = await _get_or_create_tender_id("17269797-1", _SAMPLE_TRDBUY)

    # User 1 creates application
    create_resp = await authed.post(
        "/api/applications",
        json={"tender_id": tender_id, "lots_data": _SAMPLE_LOTS},
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    # User 1 can access their own application
    own_resp = await authed.get(f"/api/applications/{app_id}")
    assert own_resp.status_code == 200

    # User 2 gets 404 (not 403) — IDOR mitigation T-05-01
    other_resp = await authed2.get(f"/api/applications/{app_id}")
    assert other_resp.status_code == 404


@pytest.mark.asyncio
async def test_get_application_not_found_returns_404(authed):
    """GET /api/applications/{id} returns 404 for non-existent ID."""
    resp = await authed.get("/api/applications/999999")
    assert resp.status_code == 404
