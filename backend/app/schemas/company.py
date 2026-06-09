"""Pydantic schemas for company profile endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.services.bin_validator import validate_bin


class CompanyProfileRequest(BaseModel):
    bin: str = Field(min_length=12, max_length=12)
    company_name: str = Field(min_length=1, max_length=500)
    legal_address: str = Field(min_length=1, max_length=1000)

    @field_validator("bin")
    @classmethod
    def bin_must_be_valid(cls, v: str) -> str:
        if not validate_bin(v):
            raise ValueError("Некорректный БИН")
        return v


class CompanyProfileResponse(BaseModel):
    model_config = {"from_attributes": True}

    bin: Optional[str] = None
    company_name: Optional[str] = None
    legal_address: Optional[str] = None
    updated_at: Optional[datetime] = None
