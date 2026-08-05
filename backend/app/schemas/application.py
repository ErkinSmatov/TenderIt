"""Pydantic schemas for Application endpoints.

ApplicationCreate — validates incoming request body for POST /api/applications.
ApplicationResponse — response schema for application CRUD.

Security:
- ApplicationCreate NEVER contains user_id — it MUST come from JWT (T-05-02).
- lots_data validated non-empty at entry point (T-05-05 input validation).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class LotOffer(BaseModel):
    """Offer for a single lot in a tender application.

    unit_price × quantity = total_price (total_price is stored for audit;
    actual calculation and encryption happen in the browser wizard steps 6-10).
    """

    lot_id: int
    unit_price: Decimal
    quantity: int
    total_price: Decimal


class ApplicationCreate(BaseModel):
    """Request body for POST /api/applications.

    Security: user_id is NEVER accepted in this body — it is always derived
    from the JWT claim by the route handler (T-05-02 mitigation).
    """

    tender_id: int
    lots_data: list[LotOffer]
    document_ids: list[int] = []

    @field_validator("lots_data")
    @classmethod
    def lots_data_must_be_non_empty(cls, v: list[LotOffer]) -> list[LotOffer]:
        """Reject empty lots_data — a valid application requires at least one lot offer (T-05-05)."""
        if not v:
            raise ValueError("lots_data не может быть пустым — нужен хотя бы один лот")
        return v


class ApplicationPatch(BaseModel):
    """Request body for PATCH /api/applications/{id}.

    Updates lots_data and document_ids on a draft application.
    Only allowed when status == 'draft'.
    """

    lots_data: list[LotOffer]
    document_ids: list[int] = []


class ApplicationResponse(BaseModel):
    """Response schema for a single Application.

    from_attributes=True allows ORM model → Pydantic conversion.
    lots_data is stored as JSONB (list[Any]) — serialized as-is.

    tender_number_anno and tender_lots_data are denormalized from a Tender JOIN
    in GET /api/applications/{id} to support the draft-fill wizard.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    tender_id: int
    status: str
    lots_data: list[Any]
    document_ids: list[int]
    goszakup_application_id: Optional[int]
    goszakup_tender_buy_id: Optional[int]
    error_message: Optional[str]
    retry_count: int
    created_at: datetime
    ready_at: Optional[datetime]
    submitted_at: Optional[datetime]

    # Denormalized from Tender JOIN — populated by GET /api/applications/{id}
    tender_number_anno: Optional[str] = None
    tender_lots_data: Optional[list[Any]] = None
