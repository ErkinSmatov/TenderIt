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
import io
import os
import uuid
from datetime import datetime, timedelta, timezone as tz

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

# File type allowlist (CR-02 mitigation — T-04-02)
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
}


@router.post("/documents", status_code=201, response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    category: DocumentCategory = Form(...),
    expires_at: datetime | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Upload a document to the vault.

    File content is read into memory with a streaming size check (CR-01: size guard
    is always enforced regardless of whether the client sends Content-Length).
    File type is validated against allowlist before upload (CR-02 mitigation).
    MinIO upload is followed by DB insert with rollback on DB failure (WR-03).

    Object key: documents/{user_id}/{uuid4}{ext} — uuid4 prevents path traversal (T-04-03).
    user_id comes from JWT, never from request body (T-04-05 mitigation).
    """
    # CR-02: Validate file extension and MIME type against allowlist (415 Unsupported Media Type)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Тип файла не поддерживается")
    ct = file.content_type or ""
    if ct not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Тип файла не поддерживается")

    # WR-02: Normalize naive expires_at to UTC before any comparison or storage
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=tz.utc)

    # CR-01: Read stream in chunks to enforce 20 MB limit regardless of Content-Length header
    # (T-04-02 mitigation — file.size may be None when client omits part Content-Length)
    CHUNK = 64 * 1024
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Файл превышает 20 МБ")
        chunks.append(chunk)

    data = b"".join(chunks)

    # Build object key with uuid4 (T-04-03: path traversal mitigation)
    object_key = f"documents/{current_user.id}/{uuid.uuid4()}{ext}"

    # Upload to MinIO; access via module reference so unit tests can patch _minio_client
    await asyncio.to_thread(
        minio_service._minio_client.put_object,
        minio_service.BUCKET_NAME,
        object_key,
        io.BytesIO(data),
        len(data),
        ct,
    )

    # WR-03: Rollback MinIO object if DB insert fails to avoid orphaned files
    try:
        doc = await create_document(
            db=db,
            user_id=current_user.id,  # ALWAYS from JWT (T-04-05)
            file_name=file.filename or "unknown",
            file_key=object_key,
            file_size=len(data),  # WR-05: actual bytes, never 0
            mime_type=ct,
            category=category.value,
            expires_at=expires_at,
        )
    except Exception:
        await asyncio.to_thread(
            minio_service._minio_client.remove_object,
            minio_service.BUCKET_NAME,
            object_key,
        )
        raise HTTPException(status_code=500, detail="Ошибка при сохранении документа")
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
    # CR-03: use model_fields_set to distinguish omitted from explicit null —
    # allows clearing expires_at by sending {"expires_at": null}
    if "expires_at" in body.model_fields_set:
        new_expires = body.expires_at
        # WR-02: normalize naive datetime to UTC before storing
        if new_expires is not None and new_expires.tzinfo is None:
            new_expires = new_expires.replace(tzinfo=tz.utc)
        doc.expires_at = new_expires

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
