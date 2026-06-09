"""Company profile service — upsert logic."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_profile import CompanyProfile
from app.schemas.company import CompanyProfileRequest

# Re-export validate_bin so callers can import from one place
from app.services.bin_validator import validate_bin as validate_bin  # noqa: F401


async def upsert_company_profile(
    db: AsyncSession,
    user_id: int,
    data: CompanyProfileRequest,
) -> CompanyProfile:
    """Create or update a CompanyProfile for the given user_id.

    Always selects first to prevent duplicate rows (unique constraint on user_id).
    If a race condition causes an IntegrityError, the DB constraint will catch it.
    """
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if profile is not None:
        profile.bin = data.bin
        profile.company_name = data.company_name
        profile.legal_address = data.legal_address
    else:
        profile = CompanyProfile(
            user_id=user_id,
            bin=data.bin,
            company_name=data.company_name,
            legal_address=data.legal_address,
        )
        db.add(profile)

    await db.commit()
    await db.refresh(profile)
    return profile
