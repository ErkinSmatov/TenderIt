"""Pydantic schemas for Document endpoints.

DocumentCategory — 5 fixed categories stored as TEXT in DB (not PG ENUM).
ExpiryStatus — computed in service layer, not stored in DB.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class DocumentCategory(str, Enum):
    """Document category — 5 fixed values (Decision 2 in CONTEXT.md).

    Stored as VARCHAR(50) in DB to allow easy v2 extension without ALTER TYPE.
    Validated by Pydantic on input; serialized as the string value.
    """

    USTAV = "ustav"
    LICENSE = "license"
    CERTIFICATE = "certificate"
    REGISTRATION = "registration"
    OTHER = "other"


# Expiry status — computed by compute_expiry_status() in document_service.py
# ok         — expires_at IS NULL or expires > 14 days
# warning_14 — expires in 8-14 days
# warning_7  — expires in 1-7 days
# expired    — expires_at < now()
ExpiryStatus = Literal["ok", "warning_14", "warning_7", "expired"]


class DocumentResponse(BaseModel):
    """Response schema for a single document.

    expiry_status is NOT in the ORM model — it is added by the service layer
    before returning the response (compute_expiry_status on expires_at).
    """

    model_config = {"from_attributes": True}

    id: int
    file_name: str
    file_key: str
    file_size: int
    mime_type: str
    category: DocumentCategory
    expires_at: datetime | None
    uploaded_at: datetime
    expiry_status: ExpiryStatus


class DocumentPatchRequest(BaseModel):
    """Partial update for document metadata (category and/or expiry date)."""

    category: DocumentCategory | None = None
    expires_at: datetime | None = None
