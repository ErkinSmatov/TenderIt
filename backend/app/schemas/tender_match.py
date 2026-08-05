"""Pydantic schemas for TenderMatch endpoints (discovery feed).

TenderMatchResponse — response schema for GET /api/discovery/matches.

Tender fields (name_ru, customer_name_ru, total_sum, end_date, region) are denormalized
for frontend use — populated by JOIN in the discovery router.
end_date IS the submission deadline (see 07-RESEARCH.md Pitfall 4; no deadline_at column).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TenderMatchResponse(BaseModel):
    """Response schema for a single TenderMatch (discovery feed entry).

    from_attributes=True allows ORM TenderMatch → Pydantic conversion.
    Tender fields are nullable — populated by JOIN in the discovery router;
    if the tender is somehow missing they fall back to None.
    """

    model_config = ConfigDict(from_attributes=True)

    # TenderMatch core fields
    id: int
    user_id: int
    tender_id: int
    status: str
    notified_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    created_at: datetime

    # Tender fields denormalized for frontend display (D-12: TenderMatchCard)
    # These are populated by the discovery router via JOIN; not on the ORM model itself
    tender_name_ru: Optional[str] = None
    customer_name_ru: Optional[str] = None
    total_sum: Optional[Decimal] = None
    # end_date = submission deadline (tender.end_date, NOT a separate deadline_at column)
    end_date: Optional[datetime] = None
    region: Optional[str] = None


class TenderMatchListResponse(BaseModel):
    """Paginated response for GET /api/discovery/matches."""

    items: list[TenderMatchResponse]
    total: int
    page: int
    page_size: int
