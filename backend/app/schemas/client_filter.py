"""Pydantic schemas for ClientFilter endpoints.

ClientFilterCreate — validates incoming PUT /api/discovery/filters request body.
ClientFilterResponse — response schema for GET /api/discovery/filters.

Security:
- ClientFilterCreate NEVER contains user_id — it MUST come from JWT (mirrors T-05-02 pattern).
- keywords validated max 20 items (T-07-04 DoS guard).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ClientFilterCreate(BaseModel):
    """Request body for PUT /api/discovery/filters.

    Security: user_id is NEVER accepted in this body — derived from JWT.
    All fields are optional with empty/None defaults — partial filter is valid.
    """

    keywords: list[str] = []
    spgz_codes: list[str] = []
    region: Optional[str] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None

    @field_validator("keywords")
    @classmethod
    def keywords_max_20(cls, v: list[str]) -> list[str]:
        """Reject keyword lists longer than 20 items (T-07-04 DoS guard).

        Parameterized ILIKE queries prevent SQL injection; this guard limits
        the number of ILIKE clauses generated per matching run.
        """
        if len(v) > 20:
            raise ValueError(
                f"keywords не может содержать более 20 элементов (получено {len(v)})"
            )
        return v


class ClientFilterResponse(ClientFilterCreate):
    """Response schema for GET /api/discovery/filters.

    from_attributes=True allows ORM ClientFilter → Pydantic conversion.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
