"""Applications router — auth-gated CRUD for tender applications.

Routes:
  POST  /api/applications       — create a draft application (201)
  GET   /api/applications       — list current user's applications (200)
  GET   /api/applications/{id}  — get single application with tender info (200 or 404)
  PATCH /api/applications/{id}  — update lots_data + document_ids on a draft (200)

Security invariants (CLAUDE.md + 05-CONTEXT.md):
- All routes require JWT auth (get_current_user dependency).
- user_id is ALWAYS from current_user.id (JWT claim), NEVER from request body (T-05-02).
- GET /api/applications/{id} uses get_user_application() which filters by user_id:
  returns 404 for another user's application (not 403) to avoid leaking existence (T-05-01).
- Input validation: lots_data validated non-empty by ApplicationCreate schema (T-05-05).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.application import Application
from app.models.tender import Tender
from app.models.user import User
from app.schemas.application import ApplicationCreate, ApplicationPatch, ApplicationResponse
from app.services.application_service import (
    create_application,
    get_user_application,
    list_user_applications,
    to_response,
)

router = APIRouter()


def _to_response_with_tender(app: Application, tender: Tender | None) -> ApplicationResponse:
    resp = to_response(app)
    if tender:
        resp.tender_number_anno = tender.number_anno
        resp.tender_lots_data = tender.lots_data
    return resp


@router.post("/applications", status_code=201, response_model=ApplicationResponse)
async def create_application_route(
    body: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """Create a draft tender application for the authenticated user.

    Security:
    - user_id comes from JWT (current_user.id), NEVER from body (T-05-02 mitigation).
    - lots_data validated non-empty by ApplicationCreate schema (T-05-05).

    Returns 201 with the created application.
    """
    app = await create_application(
        db=db,
        user_id=current_user.id,  # ALWAYS from JWT — T-05-02
        data=body,
    )
    return to_response(app)


@router.get("/applications", response_model=list[ApplicationResponse])
async def list_applications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationResponse]:
    """List all applications for the authenticated user, newest first.

    Only returns applications owned by the current user — no cross-user leakage.
    """
    apps = await list_user_applications(db, current_user.id)
    return [to_response(a) for a in apps]


@router.get("/applications/{app_id}", response_model=ApplicationResponse)
async def get_application(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """Get a single application by ID, with denormalized tender fields for the draft wizard.

    IDOR-safe: returns 404 (not 403) when the application belongs to another user
    to avoid leaking existence (T-05-01 mitigation).

    Joins with Tender to populate tender_number_anno and tender_lots_data — used by
    the draft-fill wizard on /applications/{id} when status == 'draft'.
    """
    result = await db.execute(
        select(Application, Tender)
        .outerjoin(Tender, Application.tender_id == Tender.id)
        .where(Application.id == app_id, Application.user_id == current_user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    app, tender = row
    return _to_response_with_tender(app, tender)


@router.patch("/applications/{app_id}", response_model=ApplicationResponse)
async def patch_application(
    app_id: int,
    body: ApplicationPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """Update lots_data and document_ids on a draft application.

    Only allowed when status == 'draft' — returns 409 otherwise.
    IDOR-safe: 404 when app belongs to another user (T-05-01).
    """
    result = await db.execute(
        select(Application, Tender)
        .outerjoin(Tender, Application.tender_id == Tender.id)
        .where(Application.id == app_id, Application.user_id == current_user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    app, tender = row

    if app.status != "draft":
        raise HTTPException(status_code=409, detail="Редактировать можно только черновик")

    app.lots_data = [
        {
            "lot_id": offer.lot_id,
            "unit_price": str(offer.unit_price),
            "quantity": offer.quantity,
            "total_price": str(offer.total_price),
        }
        for offer in body.lots_data
    ]
    app.document_ids = body.document_ids
    await db.commit()
    await db.refresh(app)
    return _to_response_with_tender(app, tender)
