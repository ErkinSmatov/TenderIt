"""Pydantic schemas for tender lookup and watchlist endpoints.

Design notes (03-CONTEXT.md, Decision 3):
- WatchlistAddRequest uses Field(min_length, max_length) + whitespace strip.
- NO regex on numberAnno — SPIKE-01 confirmed format "{digits}-{digits}" but
  variations are possible. Gate is: non-empty ≤ 100 chars after strip.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class LotItem(BaseModel):
    model_config = {"from_attributes": True}

    lot_number: Optional[str] = None
    name_ru: Optional[str] = None
    name_kz: Optional[str] = None
    description_ru: Optional[str] = None
    amount: Optional[Any] = None


class TenderResponse(BaseModel):
    model_config = {"from_attributes": True}

    number_anno: str
    name_ru: Optional[str] = None
    name_kz: Optional[str] = None
    total_sum: Optional[Any] = None
    customer_name_ru: Optional[str] = None
    customer_name_kz: Optional[str] = None
    # refBuyStatusId: 220 = "Опубликовано (прием заявок)" / PublishedOrderTaking (SPIKE-01)
    status_id: Optional[int] = None
    status_name_ru: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    publish_date: Optional[datetime] = None
    lots_data: Optional[list[Any]] = None
    cached_at: datetime


class WatchlistAddRequest(BaseModel):
    number_anno: str = Field(min_length=1, max_length=100)

    @field_validator("number_anno")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace from the tender number."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Номер тендера не может быть пустым")
        return stripped


class WatchlistEntryResponse(BaseModel):
    model_config = {"from_attributes": True}

    tender: TenderResponse
    notification_on: bool
    added_at: datetime
