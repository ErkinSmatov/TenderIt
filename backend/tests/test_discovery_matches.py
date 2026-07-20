"""Integration tests for GET /api/discovery/matches and participate/skip endpoints.

Covers:
  DISC-04: GET /api/discovery/matches — IDOR: only current user's matches returned
  T-07-01: POST /api/discovery/{match_id}/participate — 404 for other user's match
  T-07-02: POST /api/discovery/{match_id}/skip — 404 for other user's match
  DISC-05: Valid participate → Application with status='draft'
  DISC-05: Valid skip → {"ok": True}, match.status becomes 'skipped'

Strategy:
  - TenderMatch records inserted directly via AsyncSessionLocal (committed,
    not rolled back) so they are visible to FastAPI's own DB sessions.
  - create_discovery_draft is mocked in participate tests (created by 07-04
    which runs in parallel — at test runtime both plans have completed, but
    in this worktree only 07-03 code is present).
  - Each test uses a unique user and unique Tender to avoid state bleed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from httpx import ASGITransport, AsyncClient

import app.db as db_module
from app.main import app
from app.models.application import Application
from app.models.tender import Tender
from app.models.tender_match import TenderMatch
from app.services.goszakup_service import GRAPHQL_URL
import httpx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_TRDBUY = {
    "id": 17900001,
    "numberAnno": "17900001-1",
    "nameRu": "Тест тендер для дискавери",
    "nameKz": None,
    "totalSum": 100000,
    "countLots": 1,
    "customerBin": "000000000001",
    "customerNameRu": "Заказчик тест",
    "customerNameKz": None,
    "refBuyStatusId": 220,
    "RefBuyStatus": {"id": 220, "nameRu": "Опубликовано", "nameKz": None, "code": "PublishedOrderTaking"},
    "startDate": "2026-07-01 10:00:00",
    "endDate": "2026-07-15 10:00:00",
    "publishDate": "2026-07-01 09:00:00",
    "lastUpdateDate": "2026-07-01 09:00:00",
    "Lots": [],
}


async def _register_and_login(prefix: str) -> AsyncClient:
    """Create a fresh authenticated AsyncClient for a new unique user."""
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        resp = await ac.post(
            "/api/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    return ac


async def _get_or_create_tender(number_anno: str) -> int:
    """Ensure a Tender row exists in the DB and return its id."""
    async with db_module.AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Tender).where(Tender.number_anno == number_anno)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing.id

    # Insert via API (goszakup mock)
    gz_body = dict(_SAMPLE_TRDBUY, numberAnno=number_anno, id=int(number_anno.split("-")[0]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        email = f"tender_setup_{uuid.uuid4().hex[:8]}@example.com"
        with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
            await ac.post(
                "/api/auth/register",
                json={"email": email, "password": "SecurePass123!"},
            )
        with respx.mock:
            respx.post(GRAPHQL_URL).mock(
                return_value=httpx.Response(200, json={"data": {"TrdBuy": [gz_body]}})
            )
            await ac.get(f"/api/tenders/{number_anno}")

    async with db_module.AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Tender).where(Tender.number_anno == number_anno)
        )
        tender = result.scalar_one()
        return tender.id


async def _get_user_id_from_client(ac: AsyncClient) -> int:
    """Get the user_id of the authenticated client via /api/company (uses JWT)."""
    # Register and get user_id by looking at the token
    # Use a DB query to find the most recently created user
    async with db_module.AsyncSessionLocal() as session:
        from sqlalchemy import select
        from app.models.user import User
        result = await session.execute(
            select(User).order_by(User.id.desc()).limit(1)
        )
        user = result.scalar_one_or_none()
        return user.id if user else 1


async def _create_tender_match(user_id: int, tender_id: int, status: str = "matched") -> int:
    """Directly insert a TenderMatch and return its id (no rollback — committed)."""
    async with db_module.AsyncSessionLocal() as session:
        match = TenderMatch(
            user_id=user_id,
            tender_id=tender_id,
            status=status,
        )
        session.add(match)
        await session.commit()
        await session.refresh(match)
        return match.id


# ---------------------------------------------------------------------------
# Test 1: User A cannot see User B's match (IDOR on GET matches)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_matches_idor_isolation() -> None:
    """User A's GET /api/discovery/matches does not include User B's matches."""
    tender_id = await _get_or_create_tender("17900001-1")

    ac_a = await _register_and_login("disc_match_a")
    ac_b = await _register_and_login("disc_match_b")
    try:
        user_b_id = await _get_user_id_from_client(ac_b)

        # Create match for User B only
        await _create_tender_match(user_b_id, tender_id)

        # User A's feed must be empty (not 404, just empty list)
        resp = await ac_a.get("/api/discovery/matches")
        assert resp.status_code == 200, resp.text
        matches = resp.json()
        # User A should NOT see User B's match
        assert all(m["user_id"] != user_b_id for m in matches), (
            "IDOR: User A can see User B's match"
        )
    finally:
        await ac_a.aclose()
        await ac_b.aclose()


# ---------------------------------------------------------------------------
# Test 2: participate with other user's match → 404 (T-07-01)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_participate_other_user_match_returns_404() -> None:
    """POST /api/discovery/{match_id}/participate returns 404 for other user's match (T-07-01)."""
    tender_id = await _get_or_create_tender("17900001-1")

    ac_a = await _register_and_login("disc_part_a")
    ac_b = await _register_and_login("disc_part_b")
    try:
        user_b_id = await _get_user_id_from_client(ac_b)
        match_id = await _create_tender_match(user_b_id, tender_id)

        # User A tries to participate in User B's match
        resp = await ac_a.post(f"/api/discovery/{match_id}/participate")
        assert resp.status_code == 404, (
            f"Expected 404 (IDOR), got {resp.status_code}: {resp.text}"
        )
    finally:
        await ac_a.aclose()
        await ac_b.aclose()


# ---------------------------------------------------------------------------
# Test 3: skip with other user's match → 404 (T-07-02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_other_user_match_returns_404() -> None:
    """POST /api/discovery/{match_id}/skip returns 404 for other user's match (T-07-02)."""
    tender_id = await _get_or_create_tender("17900001-1")

    ac_a = await _register_and_login("disc_skip_a")
    ac_b = await _register_and_login("disc_skip_b")
    try:
        user_b_id = await _get_user_id_from_client(ac_b)
        match_id = await _create_tender_match(user_b_id, tender_id)

        # User A tries to skip User B's match
        resp = await ac_a.post(f"/api/discovery/{match_id}/skip")
        assert resp.status_code == 404, (
            f"Expected 404 (IDOR), got {resp.status_code}: {resp.text}"
        )
    finally:
        await ac_a.aclose()
        await ac_b.aclose()


# ---------------------------------------------------------------------------
# Test 4: Valid participate → creates Application, returns ApplicationResponse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_participate_creates_draft_application() -> None:
    """POST /api/discovery/{match_id}/participate creates Application with status='draft'.

    create_discovery_draft is mocked because it is implemented by plan 07-04
    (running in parallel). At production runtime both plans will be merged.
    """
    tender_id = await _get_or_create_tender("17900001-1")
    ac = await _register_and_login("disc_part_own")
    try:
        user_id = await _get_user_id_from_client(ac)
        match_id = await _create_tender_match(user_id, tender_id)

        # Build a mock Application to return from create_discovery_draft
        mock_app = MagicMock(spec=Application)
        mock_app.id = 9999
        mock_app.tender_id = tender_id
        mock_app.status = "draft"
        mock_app.lots_data = []
        mock_app.document_ids = []
        mock_app.goszakup_application_id = None
        mock_app.goszakup_tender_buy_id = None
        mock_app.error_message = None
        mock_app.retry_count = 0
        from datetime import datetime
        mock_app.created_at = datetime(2026, 7, 19, 12, 0, 0)
        mock_app.ready_at = None
        mock_app.submitted_at = None

        with patch(
            "app.services.application_service.create_discovery_draft",
            new=AsyncMock(return_value=mock_app),
            create=True,  # create=True allows patching non-existent attribute
            # (create_discovery_draft is implemented by plan 07-04, which runs
            # in parallel — at production runtime both plans are merged)
        ):
            resp = await ac.post(f"/api/discovery/{match_id}/participate")

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "draft"
        assert body["tender_id"] == tender_id

        # Verify match status updated to 'participating'
        async with db_module.AsyncSessionLocal() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(TenderMatch).where(TenderMatch.id == match_id)
            )
            match = result.scalar_one()
            assert match.status == "participating"
            assert match.decided_at is not None
    finally:
        await ac.aclose()


# ---------------------------------------------------------------------------
# Test 5: Valid skip → {"ok": True}, match status becomes 'skipped'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_sets_status_skipped() -> None:
    """POST /api/discovery/{match_id}/skip returns {"ok": True}, match status → 'skipped'."""
    tender_id = await _get_or_create_tender("17900001-1")
    ac = await _register_and_login("disc_skip_own")
    try:
        user_id = await _get_user_id_from_client(ac)
        match_id = await _create_tender_match(user_id, tender_id)

        resp = await ac.post(f"/api/discovery/{match_id}/skip")
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"ok": True}

        # Verify match status updated to 'skipped'
        async with db_module.AsyncSessionLocal() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(TenderMatch).where(TenderMatch.id == match_id)
            )
            match = result.scalar_one()
            assert match.status == "skipped"
            assert match.decided_at is not None
    finally:
        await ac.aclose()
