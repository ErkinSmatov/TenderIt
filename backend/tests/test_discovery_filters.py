"""Integration tests for GET/PUT /api/discovery/filters.

Covers:
  DISC-01: PUT /api/discovery/filters — create and replace filter set
  DISC-01: GET /api/discovery/filters — return current filter set
  D-10:    Upsert semantics — second PUT replaces first
  Auth:    Unauthenticated requests return 401
  Edge:    GET with no filter returns 404

Strategy:
  - All tests use AsyncClient (ASGITransport) for HTTP operations.
  - Each test registers a new unique user to prevent state bleed.
  - No direct DB access needed — the router handles all DB operations.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login(prefix: str = "discfilt") -> AsyncClient:
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


# ---------------------------------------------------------------------------
# Test 1: PUT creates new filter — returns 200 with ClientFilterResponse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_creates_filter() -> None:
    """PUT /api/discovery/filters creates a new filter and returns it."""
    ac = await _register_and_login(prefix="disc_create")
    try:
        resp = await ac.put(
            "/api/discovery/filters",
            json={"keywords": ["тест"], "spgz_codes": [], "region": None},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["keywords"] == ["тест"]
        assert "id" in body
        assert "user_id" in body
    finally:
        await ac.aclose()


# ---------------------------------------------------------------------------
# Test 2: GET returns saved filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_saved_filter() -> None:
    """GET /api/discovery/filters returns the filter saved by PUT."""
    ac = await _register_and_login(prefix="disc_get")
    try:
        # Create filter
        put_resp = await ac.put(
            "/api/discovery/filters",
            json={"keywords": ["тест"], "spgz_codes": [], "region": "Алматы"},
        )
        assert put_resp.status_code == 200

        # GET should return the same data
        get_resp = await ac.get("/api/discovery/filters")
        assert get_resp.status_code == 200, get_resp.text
        body = get_resp.json()
        assert body["keywords"] == ["тест"]
        assert body["region"] == "Алматы"
    finally:
        await ac.aclose()


# ---------------------------------------------------------------------------
# Test 3: Second PUT replaces first (upsert semantics, D-10)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_second_put_replaces_first() -> None:
    """Second PUT completely replaces the first filter (D-10: upsert semantics)."""
    ac = await _register_and_login(prefix="disc_upsert")
    try:
        # First PUT
        resp1 = await ac.put(
            "/api/discovery/filters",
            json={"keywords": ["тест"], "spgz_codes": [], "region": None},
        )
        assert resp1.status_code == 200

        # Second PUT — different keywords
        resp2 = await ac.put(
            "/api/discovery/filters",
            json={"keywords": ["новый"], "spgz_codes": ["12.34.56"], "region": None},
        )
        assert resp2.status_code == 200

        # GET should return the SECOND PUT's data, not the first
        get_resp = await ac.get("/api/discovery/filters")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["keywords"] == ["новый"]
        assert body["spgz_codes"] == ["12.34.56"]
    finally:
        await ac.aclose()


# ---------------------------------------------------------------------------
# Test 4: GET on fresh user with no filter returns 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_no_filter_returns_404() -> None:
    """GET /api/discovery/filters returns 404 when no filter has been set."""
    ac = await _register_and_login(prefix="disc_nofilt")
    try:
        resp = await ac.get("/api/discovery/filters")
        assert resp.status_code == 404, resp.text
    finally:
        await ac.aclose()


# ---------------------------------------------------------------------------
# Test 5: Unauthenticated GET returns 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated_get_returns_401() -> None:
    """Unauthenticated GET /api/discovery/filters returns 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as anon:
        resp = await anon.get("/api/discovery/filters")
    assert resp.status_code == 401
