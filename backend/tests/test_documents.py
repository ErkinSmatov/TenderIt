"""Phase 4 Document Vault — test scaffold.

Wave 0: test_expiry_status_logic (pure unit, no DB/MinIO needed) — GREEN.
Wave 1 tests (Plan 02): test_upload_*, test_delete_*, test_get_*, test_attachable_*
  — stubs marked with pytest.mark.skip until Plan 02 implements the router.

Fixtures:
  authed  — function-scoped authenticated AsyncClient (user prefix "doctest")
  authed2 — second authenticated AsyncClient (user prefix "doctest2")
  Used by Wave 1 tests for IDOR and user-isolation testing.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app

# ---------------------------------------------------------------------------
# Fixtures (same pattern as test_tenders.py)
# ---------------------------------------------------------------------------


async def _register_and_login(prefix: str = "doctest") -> AsyncClient:
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
    """Function-scoped authenticated client (user prefix: doctest)."""
    ac = await _register_and_login(prefix="doctest")
    yield ac
    await ac.aclose()


@pytest_asyncio.fixture
async def authed2():
    """Second independent authenticated client (user prefix: doctest2) for isolation tests."""
    ac = await _register_and_login(prefix="doctest2")
    yield ac
    await ac.aclose()


# ---------------------------------------------------------------------------
# Wave 0: pure unit tests (no DB/MinIO) — GREEN
# ---------------------------------------------------------------------------


def test_expiry_status_logic():
    """DOCS-03: compute_expiry_status returns correct status for all boundary dates.

    Covers 5 branches:
    - None       → "ok"
    - +30 days   → "ok"
    - +10 days   → "warning_14"
    - +5 days    → "warning_7"
    - -1 day     → "expired"
    """
    from datetime import datetime, timedelta, timezone

    from app.services.document_service import compute_expiry_status

    now = datetime.now(timezone.utc)

    assert compute_expiry_status(None) == "ok"
    assert compute_expiry_status(now + timedelta(days=30)) == "ok"
    assert compute_expiry_status(now + timedelta(days=10)) == "warning_14"
    assert compute_expiry_status(now + timedelta(days=5)) == "warning_7"
    assert compute_expiry_status(now - timedelta(days=1)) == "expired"


# ---------------------------------------------------------------------------
# Wave 1 stubs (Plan 02) — skip until router documents.py is implemented
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Plan 02: router not yet implemented")
async def test_upload_success(authed):
    """DOCS-01: POST /api/documents → 201, DB record created, MinIO put_object called."""
    # TODO Plan 02: mock _minio_client, post multipart form, assert 201 + body
    pass


@pytest.mark.skip(reason="Plan 02: router not yet implemented")
async def test_upload_too_large(authed):
    """DOCS-01: POST /api/documents with file > 20MB → 413."""
    # TODO Plan 02: post 21MB file, assert 413
    pass


@pytest.mark.skip(reason="Plan 02: router not yet implemented")
async def test_upload_invalid_category(authed):
    """DOCS-02: POST /api/documents with invalid category → 422."""
    # TODO Plan 02: post invalid category, assert 422
    pass


@pytest.mark.skip(reason="Plan 02: router not yet implemented")
async def test_delete_document(authed):
    """DOCS-04: DELETE /api/documents/{id} removes from DB and MinIO."""
    # TODO Plan 02: upload, then delete, assert 204 + MinIO remove_object called
    pass


@pytest.mark.skip(reason="Plan 02: router not yet implemented")
async def test_delete_idor_protection(authed, authed2):
    """DOCS-04: User A cannot delete User B's document → 404."""
    # TODO Plan 02: authed uploads, authed2 tries to delete, assert 404
    pass


@pytest.mark.skip(reason="Plan 02: router not yet implemented")
async def test_attachable_excludes_expired(authed):
    """DOCS-05: GET /api/documents/attachable returns only non-expired documents."""
    # TODO Plan 02: upload expired + valid, GET /attachable, assert expired excluded
    pass


@pytest.mark.skip(reason="Plan 02: router not yet implemented")
async def test_get_presigned_url(authed):
    """DOCS-01: GET /api/documents/{id}/url → 200 with pre-signed URL."""
    # TODO Plan 02: upload, get URL, assert 200 + url field present
    pass


@pytest.mark.skip(reason="Plan 02: router not yet implemented")
async def test_url_idor_protection(authed, authed2):
    """DOCS-01: User A cannot get pre-signed URL for User B's document → 404."""
    # TODO Plan 02: authed uploads, authed2 tries /url, assert 404
    pass
