"""Tender lookup and watchlist router.

Routes:
  GET  /api/tenders/{number_anno}  — lookup tender by number, 404 if not found
  POST /api/watchlist              — add tender to authenticated user's watchlist
  DELETE /api/watchlist/{number_anno} — remove from watchlist (IDOR-safe)
  GET  /api/watchlist              — list current user's watchlist

Security invariants (CLAUDE.md + 03-CONTEXT.md Decision 4):
- All routes require JWT auth (get_current_user dependency).
- user_id is ALWAYS derived from the JWT claim (current_user.id), NEVER from request body.
- DELETE filters on (user_id, number_anno) — a user cannot remove another user's entry.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.tender import TenderResponse, WatchlistAddRequest, WatchlistEntryResponse
from app.services.tender_service import (
    add_to_watchlist,
    get_or_fetch_tender,
    list_watchlist,
    remove_from_watchlist,
)

router = APIRouter()


@router.get("/tenders/{number_anno}", response_model=TenderResponse)
async def get_tender(
    number_anno: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenderResponse:
    """Look up a tender by its numberAnno (e.g. '17163708-1').

    Returns cached tender if fresh (< 30 min); otherwise fetches from goszakup.
    Returns 404 if the tender is not found on the portal.
    """
    tender = await get_or_fetch_tender(db, number_anno.strip())
    if tender is None:
        raise HTTPException(
            status_code=404,
            detail=f"Тендер с номером {number_anno} не найден на портале",
        )
    return TenderResponse.model_validate(tender)


@router.post("/watchlist", status_code=201, response_model=WatchlistEntryResponse)
async def add_watchlist_entry(
    body: WatchlistAddRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WatchlistEntryResponse:
    """Add a tender to the authenticated user's watchlist.

    Idempotent: adding the same tender twice returns 200 with the existing entry.
    user_id is derived from JWT — never from request body.
    Returns 404 if the tender does not exist in goszakup.
    """
    entry = await add_to_watchlist(db, current_user.id, body.number_anno)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Тендер с номером {body.number_anno} не найден на портале",
        )
    # Ensure the related Tender is loaded for the response
    if entry.tender is None:
        tender_result = await get_or_fetch_tender(db, body.number_anno)
        entry.tender = tender_result
    return WatchlistEntryResponse.model_validate(entry)


@router.delete("/watchlist/{number_anno}", status_code=204)
async def remove_watchlist_entry(
    number_anno: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove a tender from the authenticated user's watchlist.

    IDOR-safe: filters by (user_id, number_anno) — only own entries affected.
    Returns 204 on success, 404 if the entry does not exist for this user.
    """
    removed = await remove_from_watchlist(db, current_user.id, number_anno.strip())
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Тендер {number_anno} не найден в вашем списке отслеживания",
        )
    return Response(status_code=204)


@router.get("/watchlist", response_model=list[WatchlistEntryResponse])
async def get_watchlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WatchlistEntryResponse]:
    """Return the authenticated user's watchlist, ordered by added_at desc.

    Each entry includes full tender detail.
    Only the current user's entries are returned (no cross-user leakage).
    """
    rows = await list_watchlist(db, current_user.id)
    return [WatchlistEntryResponse.model_validate(row) for row in rows]
