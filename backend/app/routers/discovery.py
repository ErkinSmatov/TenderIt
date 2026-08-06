"""Discovery router — tender match feed and client filter management.

Routes:
  GET  /api/discovery/filters             — get current user's filter (404 if unset)
  PUT  /api/discovery/filters             — upsert filter (replaces existing)
  GET  /api/discovery/matches             — current user's match feed (newest first)
  POST /api/discovery/{match_id}/participate — mark match as participating + create draft
  POST /api/discovery/{match_id}/skip     — mark match as skipped

Security invariants (D-10, T-07-01, T-07-02, T-07-03):
- All routes require JWT auth (get_current_user dependency).
- user_id ALWAYS comes from current_user.id (JWT), NEVER from request body.
- GET /api/discovery/matches WHERE user_id = current_user.id (T-07-03).
- POST participate/skip: WHERE id=match_id AND user_id=current_user.id;
  returns 404 (not 403) on mismatch — does not leak resource existence (T-07-01/02).

create_discovery_draft is imported LAZILY inside the endpoint body (not at module
level) to avoid ImportError when plans 07-03 and 07-04 run in parallel. At runtime
both plans have completed before the endpoint is called.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.client_filter import ClientFilter
from app.models.tender import Tender
from app.models.tender_match import TenderMatch
from app.models.user import User
from app.schemas.application import ApplicationResponse
from app.schemas.client_filter import ClientFilterCreate, ClientFilterResponse
from app.schemas.tender_match import TenderMatchListResponse, TenderMatchResponse

router = APIRouter()


def _utcnow() -> datetime:
    """Return current UTC time as a NAIVE datetime (no tzinfo).

    PostgreSQL TIMESTAMP WITHOUT TIME ZONE columns require naive datetimes.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _portal_url(source: str | None, number_anno: str | None) -> str | None:
    """Compute the public portal URL for a tender based on its source.

    sk.kz URL pattern: /eprocsearch/tender/{number_anno}
    Assumed from URL structure analysis — verify by navigating to a published sk.kz tender.
    goszakup: no stable public UI URL — returns None.
    """
    if source == "sk_kz" and number_anno:
        return f"https://zakup.sk.kz/eprocsearch/tender/{number_anno}"
    return None


# ---------------------------------------------------------------------------
# 1. GET /api/discovery/filters
# ---------------------------------------------------------------------------


@router.get("/discovery/filters", response_model=ClientFilterResponse)
async def get_filters(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClientFilterResponse:
    """Return the current user's discovery filter set.

    Returns 404 if no filter has been configured yet (D-10: upsert semantics,
    no filter exists until the first PUT).
    """
    result = await db.execute(
        select(ClientFilter).where(ClientFilter.user_id == current_user.id)
    )
    cf = result.scalar_one_or_none()
    if cf is None:
        raise HTTPException(status_code=404, detail="Фильтры не настроены")
    return ClientFilterResponse.model_validate(cf)


# ---------------------------------------------------------------------------
# 2. PUT /api/discovery/filters
# ---------------------------------------------------------------------------


@router.put("/discovery/filters", response_model=ClientFilterResponse)
async def upsert_filters(
    body: ClientFilterCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClientFilterResponse:
    """Create or replace the current user's discovery filter set.

    Upsert semantics (D-10): second PUT replaces first entirely.
    user_id is ALWAYS from JWT (current_user.id), never from request body (T-05-02 pattern).
    """
    data = body.model_dump()
    stmt = (
        pg_insert(ClientFilter)
        .values(user_id=current_user.id, **data)
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "keywords": data["keywords"],
                "spgz_codes": data["spgz_codes"],
                "region": data["region"],
                "min_amount": data["min_amount"],
                "max_amount": data["max_amount"],
            },
        )
        .returning(ClientFilter)
    )
    result = await db.execute(stmt)
    cf_row = result.scalars().one()
    await db.commit()
    return ClientFilterResponse.model_validate(cf_row)


# ---------------------------------------------------------------------------
# 3. GET /api/discovery/matches
# ---------------------------------------------------------------------------


@router.get("/discovery/matches", response_model=TenderMatchListResponse)
async def get_matches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> TenderMatchListResponse:
    """Return discovery matches for the current user, newest first, with pagination.

    IDOR (T-07-03): WHERE user_id = current_user.id is enforced by SQLAlchemy;
    the endpoint NEVER accepts user_id from the request body or query params.

    Optional query params:
      status   — filter by match status (matched | notified | participating | skipped)
      page     — 1-based page number (default 1)
      page_size — items per page (default 20, max 100)
    """
    where = [TenderMatch.user_id == current_user.id]
    if status:
        where.append(TenderMatch.status == status)

    total: int = (
        await db.execute(select(func.count(TenderMatch.id)).where(*where))
    ).scalar_one()

    result = await db.execute(
        select(TenderMatch, Tender)
        .join(Tender, TenderMatch.tender_id == Tender.id, isouter=True)
        .where(*where)
        .order_by(TenderMatch.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = result.all()

    items = [
        TenderMatchResponse(
            id=match.id,
            user_id=match.user_id,
            tender_id=match.tender_id,
            status=match.status,
            notified_at=match.notified_at,
            decided_at=match.decided_at,
            created_at=match.created_at,
            tender_name_ru=tender.name_ru if tender else None,
            customer_name_ru=tender.customer_name_ru if tender else None,
            total_sum=tender.total_sum if tender else None,
            end_date=tender.end_date if tender else None,
            region=tender.region if tender else None,
            source=tender.source if tender else None,
            portal_url=_portal_url(
                tender.source if tender else None,
                tender.number_anno if tender else None,
            ),
        )
        for match, tender in rows
    ]
    return TenderMatchListResponse(items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# 4. POST /api/discovery/{match_id}/participate
# ---------------------------------------------------------------------------


@router.post(
    "/discovery/{match_id}/participate",
    status_code=201,
    response_model=ApplicationResponse,
)
async def participate(
    match_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """Mark a discovery match as 'participating' and create a draft application.

    IDOR (T-07-01): loads TenderMatch WHERE id=match_id AND user_id=current_user.id;
    returns 404 (not 403) on mismatch — does not leak resource existence.

    create_discovery_draft is imported lazily (not at module level) to avoid
    ImportError when 07-03 and 07-04 run in parallel (07-04 creates this function).
    """
    result = await db.execute(
        select(TenderMatch).where(
            TenderMatch.id == match_id,
            TenderMatch.user_id == current_user.id,  # IDOR guard (T-07-01)
        )
    )
    match = result.scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Подборка не найдена")

    if match.status in ("participating", "skipped"):
        raise HTTPException(status_code=409, detail="Уже обработано")

    # Lazy import — avoids parallel-worktree ImportError when 07-03 and 07-04
    # run simultaneously (create_discovery_draft is created by plan 07-04)
    from app.services.application_service import create_discovery_draft  # noqa: PLC0415

    app = await create_discovery_draft(db, current_user.id, match.tender_id)

    match.status = "participating"
    match.decided_at = _utcnow()
    await db.commit()

    return ApplicationResponse.model_validate(app)


# ---------------------------------------------------------------------------
# 5. POST /api/discovery/{match_id}/skip
# ---------------------------------------------------------------------------


@router.post("/discovery/{match_id}/skip")
async def skip(
    match_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Mark a discovery match as 'skipped'.

    IDOR (T-07-02): loads TenderMatch WHERE id=match_id AND user_id=current_user.id;
    returns 404 (not 403) on mismatch — does not leak resource existence.
    """
    result = await db.execute(
        select(TenderMatch).where(
            TenderMatch.id == match_id,
            TenderMatch.user_id == current_user.id,  # IDOR guard (T-07-02)
        )
    )
    match = result.scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Подборка не найдена")

    if match.status == "skipped":
        raise HTTPException(status_code=409, detail="Уже пропущено")

    match.status = "skipped"
    match.decided_at = _utcnow()
    await db.commit()

    return {"ok": True}


# ---------------------------------------------------------------------------
# 6. DELETE /api/discovery/{match_id}
# ---------------------------------------------------------------------------


@router.delete("/discovery/{match_id}", status_code=204, response_model=None)
async def delete_match(
    match_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently remove a discovery match from the user's feed.

    IDOR: WHERE id=match_id AND user_id=current_user.id; returns 404 on mismatch.
    """
    result = await db.execute(
        select(TenderMatch).where(
            TenderMatch.id == match_id,
            TenderMatch.user_id == current_user.id,
        )
    )
    match = result.scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Не найдено")
    await db.delete(match)
    await db.commit()
