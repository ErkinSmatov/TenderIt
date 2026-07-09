"""Applications router — auth-gated CRUD for tender applications.

Routes:
  POST /api/applications       — create a draft application (201)
  GET  /api/applications       — list current user's applications (200)
  GET  /api/applications/{id}  — get single application (200 or 404)

Security invariants (CLAUDE.md + 05-CONTEXT.md):
- All routes require JWT auth (get_current_user dependency).
- user_id is ALWAYS from current_user.id (JWT claim), NEVER from request body (T-05-02).
- GET /api/applications/{id} uses get_user_application() which filters by user_id:
  returns 404 for another user's application (not 403) to avoid leaking existence (T-05-01).
- Input validation: lots_data validated non-empty by ApplicationCreate schema (T-05-05).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.application import ApplicationCreate, ApplicationResponse
from app.services.application_service import (
    create_application,
    get_user_application,
    list_user_applications,
    to_response,
)

router = APIRouter()


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
    """Get a single application by ID.

    IDOR-safe: returns 404 (not 403) when the application belongs to another user
    to avoid leaking existence (T-05-01 mitigation).
    """
    app = await get_user_application(db, current_user.id, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return to_response(app)
