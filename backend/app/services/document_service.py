"""Document service — pure utility and async CRUD functions.

compute_expiry_status: pure function, no DB/MinIO access.
  Uses datetime.now(timezone.utc) — tz-aware comparison (Pitfall 7 mitigation, T-04-07).
  Must NOT use datetime.now() without timezone — would fail with TypeError in Python 3.12
  when comparing naive datetime with tz-aware datetime from TIMESTAMPTZ column.

CRUD functions: all filter by user_id to enforce IDOR protection (T-04-01 mitigation).
  user_id is ALWAYS passed from get_current_user JWT — never from request body.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.minio_service as minio_service
from app.models.document import Document

ExpiryStatus = Literal["ok", "warning_14", "warning_7", "expired"]


def compute_expiry_status(expires_at: datetime | None) -> ExpiryStatus:
    """Compute document expiry status relative to current UTC time.

    Branches:
      None              → "ok"   (permanent document, no expiry date)
      total_seconds ≤ 0 → "expired"  (WR-01: use total_seconds, not days, for expired boundary)
      days < 7          → "warning_7"
      days < 14         → "warning_14"
      days ≥ 14         → "ok"

    WR-01 fix: delta.days can be 0 for a document expiring in < 24h (but > 0 seconds),
    causing it to show "warning_7" instead of "expired". total_seconds() is the correct
    boundary check — it is negative the instant expires_at < now, regardless of sub-day values.

    Security note (T-04-07): uses datetime.now(timezone.utc) — tz-aware.
    Cannot compare tz-naive with tz-aware in Python 3.12+ (TypeError).
    TIMESTAMPTZ columns from PostgreSQL always return tz-aware datetime via asyncpg.
    """
    if expires_at is None:
        return "ok"
    now = datetime.now(timezone.utc)
    diff = expires_at - now
    if diff.total_seconds() <= 0:
        return "expired"
    days = diff.days  # safe: total_seconds > 0 so days >= 0
    if days < 7:
        return "warning_7"
    if days < 14:
        return "warning_14"
    return "ok"


async def list_user_documents(db: AsyncSession, user_id: int) -> list[Document]:
    """Return all documents for a user, ordered by uploaded_at desc.

    IDOR-safe: filters by user_id so users only see their own documents.
    """
    result = await db.execute(
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.uploaded_at.desc())
    )
    return list(result.scalars().all())


async def list_attachable_documents(db: AsyncSession, user_id: int) -> list[Document]:
    """Return non-expired documents for a user (suitable for attaching to applications).

    DOCS-05: Excludes expired documents (expires_at < now).
    Includes: documents with no expiry (permanent) and documents expiring in the future.
    IDOR-safe: filters by user_id.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Document)
        .where(
            Document.user_id == user_id,
            (Document.expires_at.is_(None)) | (Document.expires_at > now),
        )
        .order_by(Document.uploaded_at.desc())
    )
    return list(result.scalars().all())


async def get_user_document(
    db: AsyncSession, user_id: int, doc_id: int
) -> Document | None:
    """Fetch a single document by id, filtered by user_id (IDOR protection).

    Returns None if the document does not exist OR belongs to another user.
    Callers must return 404 (not 403) to avoid leaking document existence (T-04-01).
    """
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_document(
    db: AsyncSession,
    user_id: int,
    file_name: str,
    file_key: str,
    file_size: int,
    mime_type: str,
    category: str,
    expires_at: datetime | None,
) -> Document:
    """Insert a new Document record and return it.

    Security: user_id ALWAYS comes from the JWT claim (get_current_user),
    never from request body (T-04-05 mitigation).
    """
    doc = Document(
        user_id=user_id,
        file_name=file_name,
        file_key=file_key,
        file_size=file_size,
        mime_type=mime_type,
        category=category,
        expires_at=expires_at,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def delete_document(db: AsyncSession, user_id: int, doc_id: int) -> bool:
    """Delete a document from MinIO and then from the database.

    Order: MinIO FIRST, then DB (Pitfall 5 mitigation).
    If MinIO delete succeeds but DB delete fails — the file is orphaned but metadata
    is lost; this is preferable to the reverse (file exists but no way to clean it up).
    Returns True if deleted, False if document not found for this user (IDOR: 404).
    """
    doc = await get_user_document(db, user_id, doc_id)
    if doc is None:
        return False

    # MinIO first (Pitfall 5: remove_object before db.delete)
    # Access via module reference so tests can patch minio_service._minio_client
    await asyncio.to_thread(minio_service._minio_client.remove_object, minio_service.BUCKET_NAME, doc.file_key)

    await db.delete(doc)
    await db.commit()
    return True


def to_response(doc: Document) -> "DocumentResponse":
    """Convert a Document ORM instance to a DocumentResponse with computed expiry_status.

    expiry_status is NOT stored in the DB — it is computed fresh on every response
    (Pattern 6 from RESEARCH.md: service layer computation).

    Pydantic v2: model_validate with from_attributes=True + manual dict construction
    for computed fields not present in the ORM model.
    """
    from app.schemas.document import DocumentResponse

    # Build dict from ORM object, then inject expiry_status (computed field).
    # file_key is intentionally excluded from the response dict (CR-04):
    # it is an internal MinIO storage path and must not be exposed to clients.
    data = {
        "id": doc.id,
        "file_name": doc.file_name,
        "file_size": doc.file_size,
        "mime_type": doc.mime_type,
        "category": doc.category,
        "expires_at": doc.expires_at,
        "uploaded_at": doc.uploaded_at,
        "expiry_status": compute_expiry_status(doc.expires_at),
    }
    return DocumentResponse.model_validate(data)
