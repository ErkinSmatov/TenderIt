"""Document ORM model.

Stores metadata for user-uploaded documents. Actual file content is in MinIO.
Object key format: documents/{user_id}/{uuid4}{ext}

DDL source: .planning/phases/04-document-vault/04-CONTEXT.md, Decision 5.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    # user_id — always from JWT (get_current_user dep), never from request body
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Original filename for display (not used in storage path — use file_key)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    # MinIO object key: "documents/{user_id}/{uuid4}{ext}"
    file_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(200), nullable=False)
    # Stored as TEXT (not PG ENUM) for easy v2 extension — validated via Pydantic DocumentCategory
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    # nullable: NULL = no expiry (permanent document)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # No relationship to User — Phase 5 may add FK from application_documents.document_id
