"""application_service — CRUD + full state machine helpers for Application.

ALL state transition helpers are defined here (not split across plans) to prevent
cross-wave file conflicts. Plans 05-03 and 05-04 only CALL these functions.

State machine (D-05-04):
  draft → signed → waiting → submitting → submitted
                                       ↘ error (retry up to 30 min)

Security:
- user_id ALWAYS comes from get_current_user JWT claim (T-05-02).
- get_user_application filters WHERE id AND user_id — IDOR-safe (T-05-01).
- Callers must return 404 (not 403) when get_user_application returns None.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _utcnow() -> datetime:
    """Return current UTC time as a NAIVE datetime (no tzinfo).

    PostgreSQL TIMESTAMP WITHOUT TIME ZONE columns require naive datetimes.
    datetime.now(timezone.utc).replace(tzinfo=None) is the recommended approach
    (datetime.utcnow() is deprecated in Python 3.12).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)

from app.models.application import Application
from app.schemas.application import ApplicationCreate, ApplicationResponse


async def create_application(
    db: AsyncSession,
    user_id: int,
    data: ApplicationCreate,
) -> Application:
    """Insert a new Application with status='draft'.

    Security: user_id MUST come from JWT (get_current_user), never from request body (T-05-02).
    lots_data is serialized to plain list[dict] for JSONB storage.
    """
    # Convert Pydantic LotOffer objects to plain dicts for JSONB
    lots_as_dicts = [
        {
            "lot_id": offer.lot_id,
            "unit_price": str(offer.unit_price),
            "quantity": offer.quantity,
            "total_price": str(offer.total_price),
        }
        for offer in data.lots_data
    ]

    app = Application(
        user_id=user_id,
        tender_id=data.tender_id,
        lots_data=lots_as_dicts,
        document_ids=data.document_ids,
        status="draft",
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


async def list_user_applications(
    db: AsyncSession, user_id: int
) -> list[Application]:
    """Return all applications for a user, ordered by created_at desc (newest first).

    IDOR-safe: filters by user_id so users only see their own applications.
    """
    result = await db.execute(
        select(Application)
        .where(Application.user_id == user_id)
        .order_by(Application.created_at.desc())
    )
    return list(result.scalars().all())


async def get_user_application(
    db: AsyncSession, user_id: int, app_id: int
) -> Optional[Application]:
    """Fetch a single application by id, filtered by user_id (IDOR protection, T-05-01).

    Returns None if the application does not exist OR belongs to another user.
    Callers must return 404 (not 403) to avoid leaking existence.
    """
    result = await db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def mark_ready(
    db: AsyncSession,
    app: Application,
    goszakup_application_id: int,
    goszakup_tender_buy_id: int,
) -> Application:
    """Transition draft/signed → waiting.

    Called after browser completes wizard steps 1-11 and submits portal IDs.
    Sets ready_at to current UTC time.
    """
    app.status = "waiting"
    app.goszakup_application_id = goszakup_application_id
    app.goszakup_tender_buy_id = goszakup_tender_buy_id
    app.ready_at = _utcnow()
    app.updated_at = _utcnow()
    await db.commit()
    await db.refresh(app)
    return app


async def list_waiting_applications(db: AsyncSession) -> list[Application]:
    """Return all applications with status='waiting' for ARQ polling job (D-05-05).

    Used by poll_watchlist_tenders to find applications awaiting tender open.
    """
    result = await db.execute(
        select(Application).where(Application.status == "waiting")
    )
    return list(result.scalars().all())


async def mark_submitting(db: AsyncSession, app: Application) -> Application:
    """Transition waiting → submitting.

    Called when ARQ worker detects tender status_id == 220 and starts auto-submit.
    """
    app.status = "submitting"
    app.updated_at = _utcnow()
    await db.commit()
    await db.refresh(app)
    return app


async def mark_submitted(db: AsyncSession, app: Application) -> Application:
    """Transition submitting → submitted.

    Called after goszakup portal returns success for ajax_public_application.
    Sets submitted_at to current UTC time.
    """
    app.status = "submitted"
    app.submitted_at = _utcnow()
    app.updated_at = _utcnow()
    await db.commit()
    await db.refresh(app)
    return app


async def mark_error(
    db: AsyncSession, app: Application, message: str
) -> Application:
    """Transition submitting → error.

    Called when goszakup portal returns error or network failure after all retries.
    Stores the error message for display in the UI.
    """
    app.status = "error"
    app.error_message = message
    app.updated_at = _utcnow()
    await db.commit()
    await db.refresh(app)
    return app


async def increment_retry(db: AsyncSession, app: Application) -> Application:
    """Increment retry_count for exponential back-off tracking.

    Called before scheduling a retry job. Max retries enforced by the ARQ worker
    (retry up to 30 min with exponential back-off — D-05-05).
    """
    app.retry_count += 1
    app.updated_at = _utcnow()
    await db.commit()
    await db.refresh(app)
    return app


def to_response(app: Application) -> ApplicationResponse:
    """Convert an Application ORM model to ApplicationResponse schema."""
    return ApplicationResponse.model_validate(app)


async def create_discovery_draft(
    db: AsyncSession,
    user_id: int,
    tender_id: int,
) -> Application:
    """Create an Application draft from a discovery match — bypasses Pydantic schema.

    ApplicationCreate.lots_data_must_be_non_empty rejects empty lots, so this function
    constructs the Application ORM object directly (Research pitfall 1 / D-05).
    Lots are filled later via the application wizard. Status is always 'draft'.

    Called by: Telegram disc:participate handler and
    POST /api/discovery/{match_id}/participate endpoint.

    Security: user_id MUST come from JWT claim or verified Telegram chat_id (D-05).
    """
    app = Application(
        user_id=user_id,
        tender_id=tender_id,
        lots_data=[],
        document_ids=[],
        status="draft",
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app
