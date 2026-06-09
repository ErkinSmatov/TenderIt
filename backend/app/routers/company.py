"""Company profile router — GET and PUT /api/company/profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.company_profile import CompanyProfile
from app.models.user import User
from app.schemas.company import CompanyProfileRequest, CompanyProfileResponse
from app.services.company_service import upsert_company_profile

router = APIRouter()


@router.get("/profile", response_model=CompanyProfileResponse)
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyProfileResponse:
    """Return the authenticated user's company profile.

    Returns an empty-field response (all nulls) if no profile exists yet.
    """
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        return CompanyProfileResponse()
    return CompanyProfileResponse.model_validate(profile)


@router.put("/profile", response_model=CompanyProfileResponse)
async def put_profile(
    body: CompanyProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyProfileResponse:
    """Upsert the authenticated user's company profile.

    BIN validation (format + checksum) is enforced by the request schema.
    User ID is derived from the JWT — never accepted from the request body.
    """
    profile = await upsert_company_profile(db, user.id, body)
    return CompanyProfileResponse.model_validate(profile)
