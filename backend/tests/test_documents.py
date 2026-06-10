"""Phase 4 Document Vault — integration tests.

Wave 0: test_expiry_status_logic (pure unit, no DB/MinIO needed) — GREEN.
Wave 1 tests (Plan 02): test_upload_*, test_delete_*, test_get_*, test_attachable_*
  — full implementation with MinIO mocks.

Fixtures:
  authed  — function-scoped authenticated AsyncClient (user prefix "doctest")
  authed2 — second authenticated AsyncClient (user prefix "doctest2")
  Used by Wave 1 tests for IDOR and user-isolation testing.

MinIO Mock Pattern:
  patch("app.services.minio_service._minio_client") — patches the singleton at the
  module level where it lives. The router imports _minio_client from minio_service,
  so patching the source module affects all callers.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

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
# Helper: upload a document with mocked MinIO
# ---------------------------------------------------------------------------


async def _upload_doc(
    client: AsyncClient,
    filename: str = "test.pdf",
    category: str = "ustav",
    expires_at: str | None = None,
    content: bytes = b"fake pdf content",
) -> dict:
    """Upload a document and return the response body. Asserts 201."""
    data: dict = {"category": category}
    if expires_at is not None:
        data["expires_at"] = expires_at
    with patch("app.services.minio_service._minio_client") as mock_minio:
        mock_minio.put_object.return_value = MagicMock()
        mock_minio.bucket_exists.return_value = True
        resp = await client.post(
            "/api/documents",
            data=data,
            files={"file": (filename, io.BytesIO(content), "application/pdf")},
        )
    assert resp.status_code == 201, f"Upload failed: {resp.text}"
    return resp.json()


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
    from app.services.document_service import compute_expiry_status

    now = datetime.now(timezone.utc)

    assert compute_expiry_status(None) == "ok"
    assert compute_expiry_status(now + timedelta(days=30)) == "ok"
    assert compute_expiry_status(now + timedelta(days=10)) == "warning_14"
    assert compute_expiry_status(now + timedelta(days=5)) == "warning_7"
    assert compute_expiry_status(now - timedelta(days=1)) == "expired"


# ---------------------------------------------------------------------------
# Wave 1: router integration tests (Plan 02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_success(authed):
    """DOCS-01: POST /api/documents → 201, DB record created, MinIO put_object called."""
    mock_result = MagicMock()
    with patch("app.services.minio_service._minio_client") as mock_minio:
        mock_minio.put_object.return_value = mock_result
        mock_minio.bucket_exists.return_value = True

        resp = await authed.post(
            "/api/documents",
            data={"category": "ustav"},
            files={"file": ("test.pdf", io.BytesIO(b"fake pdf content"), "application/pdf")},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["category"] == "ustav"
    assert body["file_name"] == "test.pdf"
    assert "expiry_status" in body
    assert body["expiry_status"] == "ok"
    mock_minio.put_object.assert_called_once()


@pytest.mark.asyncio
async def test_upload_too_large(authed):
    """DOCS-01: POST /api/documents with file > 20MB → 413, put_object NOT called."""
    large_content = b"x" * (21 * 1024 * 1024)  # 21 MB
    with patch("app.services.minio_service._minio_client") as mock_minio:
        resp = await authed.post(
            "/api/documents",
            data={"category": "other"},
            files={"file": ("large.pdf", io.BytesIO(large_content), "application/pdf")},
        )
        mock_minio.put_object.assert_not_called()

    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_upload_invalid_category(authed):
    """DOCS-02: POST /api/documents with invalid category → 422."""
    with patch("app.services.minio_service._minio_client"):
        resp = await authed.post(
            "/api/documents",
            data={"category": "invalid_category_xyz"},
            files={"file": ("test.pdf", io.BytesIO(b"data"), "application/pdf")},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_document(authed):
    """DOCS-04: DELETE /api/documents/{id} → 204, remove_object called, row gone."""
    # Upload first
    body = await _upload_doc(authed, filename="to_delete.pdf")
    doc_id = body["id"]

    # Delete
    with patch("app.services.minio_service._minio_client") as mock_minio:
        resp = await authed.delete(f"/api/documents/{doc_id}")
        mock_minio.remove_object.assert_called_once()

    assert resp.status_code == 204

    # Verify gone: GET list should not include this doc
    list_resp = await authed.get("/api/documents")
    assert list_resp.status_code == 200
    ids = [d["id"] for d in list_resp.json()]
    assert doc_id not in ids


@pytest.mark.asyncio
async def test_delete_idor_protection(authed, authed2):
    """DOCS-04: User A cannot delete User B's document → 404."""
    # authed uploads a document
    body = await _upload_doc(authed, filename="owned.pdf")
    doc_id = body["id"]

    # authed2 tries to delete — must get 404
    with patch("app.services.minio_service._minio_client") as mock_minio:
        del_resp = await authed2.delete(f"/api/documents/{doc_id}")
        mock_minio.remove_object.assert_not_called()

    assert del_resp.status_code == 404


@pytest.mark.asyncio
async def test_attachable_excludes_expired(authed):
    """DOCS-05: GET /api/documents/attachable returns only non-expired documents."""
    # Upload expired document
    expired_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    await _upload_doc(authed, filename="expired.pdf", category="license", expires_at=expired_at)

    # Upload valid document (no expiry)
    await _upload_doc(authed, filename="valid.pdf", category="ustav")

    resp = await authed.get("/api/documents/attachable")
    assert resp.status_code == 200
    names = [d["file_name"] for d in resp.json()]
    assert "valid.pdf" in names
    assert "expired.pdf" not in names


@pytest.mark.asyncio
async def test_get_presigned_url(authed):
    """DOCS-01: GET /api/documents/{id}/url → 200 with pre-signed URL."""
    # Upload
    body = await _upload_doc(authed, filename="url_test.pdf")
    doc_id = body["id"]

    # Get pre-signed URL
    with patch("app.services.minio_service._minio_client") as mock_minio:
        mock_minio.presigned_get_object.return_value = "https://minio.example.com/presigned"
        url_resp = await authed.get(f"/api/documents/{doc_id}/url")

    assert url_resp.status_code == 200
    url_body = url_resp.json()
    assert "url" in url_body
    assert "expires_in" in url_body
    assert url_body["expires_in"] == 900
    assert url_body["url"] == "https://minio.example.com/presigned"


@pytest.mark.asyncio
async def test_url_idor_protection(authed, authed2):
    """DOCS-01: User A cannot get pre-signed URL for User B's document → 404."""
    # authed uploads
    body = await _upload_doc(authed, filename="secret.pdf")
    doc_id = body["id"]

    # authed2 tries to get URL — must get 404
    with patch("app.services.minio_service._minio_client") as mock_minio:
        url_resp = await authed2.get(f"/api/documents/{doc_id}/url")
        mock_minio.presigned_get_object.assert_not_called()

    assert url_resp.status_code == 404
