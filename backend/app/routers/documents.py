"""Documents router — 6 auth-gated routes for Document Vault.

Routes (in declaration order — attachable MUST come before /{doc_id}/url):
  POST   /documents            — upload a document (multipart/form-data)
  GET    /documents            — list current user's documents
  GET    /documents/attachable — list non-expired documents (for Phase 5 application attach)
  GET    /documents/{doc_id}/url  — get a pre-signed URL for download (TTL 15 min)
  PATCH  /documents/{doc_id}   — update metadata (category and/or expires_at)
  DELETE /documents/{doc_id}   — hard delete (MinIO + DB)

Security invariants (CLAUDE.md + 04-CONTEXT.md):
  - All routes require JWT auth (get_current_user dependency).
  - user_id is ALWAYS from current_user.id (JWT claim), NEVER from request body (T-04-05).
  - Routes with doc_id use get_user_document() which filters by user_id — returns 404
    for another user's document (not 403) to avoid leaking existence (T-04-01).
  - File size is validated BEFORE MinIO upload — 413 for > 20 MB (T-04-02).
  - Object key uses uuid4 — path traversal impossible (T-04-03).

Critical route ordering (RESEARCH.md Finding #4):
  'attachable' must be declared BEFORE '/{doc_id}/url' or FastAPI will match
  the literal string "attachable" as a {doc_id} path parameter.

MinIO Mock Note:
  _minio_client is accessed via app.services.minio_service._minio_client
  (module-level attribute reference) — NOT via a direct from-import.
  This allows test patches on app.services.minio_service._minio_client to work.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.minio_service as minio_service
from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.document import DocumentCategory, DocumentPatchRequest, DocumentResponse
from app.services.document_service import (
    create_document,
    delete_document,
    get_user_document,
    list_attachable_documents,
    list_user_documents,
    to_response,
)

router = APIRouter()

# 20 MB limit — validated before MinIO upload (T-04-02 mitigation)
MAX_FILE_SIZE = 20 * 1024 * 1024


@router.post("/documents", status_code=201, response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    category: DocumentCategory = Form(...),
    expires_at: datetime | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Upload a document to the vault.

    File is streamed directly to MinIO — NOT read into memory (Pitfall 4 mitigation).
    Size is checked via UploadFile.size (populated by Starlette multipart parser)
    BEFORE calling put_object (T-04-02 mitigation).

    Object key: documents/{user_id}/{uuid4}{ext} — uuid4 prevents path traversal (T-04-03).
    user_id comes from JWT, never from request body (T-04-05 mitigation).
    """
    # Validate size BEFORE MinIO upload (T-04-02: DoS mitigation)
    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Файл превышает 20 МБ")

    # Build object key with uuid4 (T-04-03: path traversal mitigation)
    ext = os.path.splitext(file.filename or "")[1].lower()
    object_key = f"documents/{current_user.id}/{uuid.uuid4()}{ext}"

    # Stream to MinIO — do NOT call file.read() before this (Pitfall 4)
    # file.file is a SpooledTemporaryFile seeked to position 0 by Starlette
    # Access via module reference so unit tests can patch minio_service._minio_client
    await asyncio.to_thread(
        minio_service._minio_client.put_object,
        minio_service.BUCKET_NAME,
        object_key,
        file.file,
        file.size if file.size is not None else -1,
        file.content_type or "application/octet-stream",
    )

    doc = await create_document(
        db=db,
        user_id=current_user.id,  # ALWAYS from JWT (T-04-05)
        file_name=file.filename or "unknown",
        file_key=object_key,
        file_size=file.size or 0,
        mime_type=file.content_type or "application/octet-stream",
        category=category.value,
        expires_at=expires_at,
    )
    return to_response(doc)


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    """List all documents for the authenticated user, ordered by upload date desc.

    Each item includes computed expiry_status (ok/warning_14/warning_7/expired).
    Only the current user's documents are returned — no cross-user leakage.
    """
    docs = await list_user_documents(db, current_user.id)
    return [to_response(d) for d in docs]


# CRITICAL: /documents/attachable MUST be declared before /documents/{doc_id}/url
# (RESEARCH.md Finding #4 — FastAPI route matching is declaration-order dependent)


@router.get("/documents/attachable", response_model=list[DocumentResponse])
async def list_attachable(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    """List non-expired documents for the authenticated user (DOCS-05).

    Returns documents suitable for attaching to a tender application (Phase 5).
    Excludes: documents where expires_at < now (expired).
    Includes: documents with no expiry (permanent) + documents expiring in the future.
    """
    docs = await list_attachable_documents(db, current_user.id)
    return [to_response(d) for d in docs]


@router.get("/documents/{doc_id}/url")
async def get_document_url(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a pre-signed MinIO URL for downloading a document.

    URL TTL: 15 minutes (900 seconds) — as per CONTEXT.md Decision 7.
    IDOR-safe: get_user_document returns 404 for another user's document (T-04-01).
    """
    doc = await get_user_document(db, current_user.id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Документ не найден")

    url: str = await asyncio.to_thread(
        minio_service._minio_client.presigned_get_object,
        minio_service.BUCKET_NAME,
        doc.file_key,
        timedelta(minutes=15),
    )
    return {"url": url, "expires_in": 900}


@router.patch("/documents/{doc_id}", response_model=DocumentResponse)
async def patch_document(
    doc_id: int,
    body: DocumentPatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Update document metadata (category and/or expires_at).

    Partial update: only non-None fields in body are applied.
    IDOR-safe: get_user_document returns 404 for another user's document (T-04-01).
    """
    doc = await get_user_document(db, current_user.id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Документ не найден")

    if body.category is not None:
        doc.category = body.category.value
    if body.expires_at is not None:
        doc.expires_at = body.expires_at

    await db.commit()
    await db.refresh(doc)
    return to_response(doc)


@router.delete("/documents/{doc_id}", status_code=204)
async def remove_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Hard-delete a document from MinIO and the database.

    MinIO object is deleted FIRST, then DB row (Pitfall 5 mitigation).
    Returns 204 on success, 404 if not found or belongs to another user (T-04-01).
    """
    removed = await delete_document(db, current_user.id, doc_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return Response(status_code=204)
