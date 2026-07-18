"""goszakup_proxy router — backend proxy for v3bl.goszakup.gov.kz wizard steps.

This router is registered at prefix="/api/goszakup" (see app/routers registration).

Architecture (D-05-01 + D-05-02, SPIKE-03 confirmed):
- Browser executes wizard steps 1-11 via TenderIt backend proxy.
  Backend proxies each step because browser cannot do cross-origin XHR to goszakup
  and read the httpOnly PHPSESSID response cookie.
- Step 12 (final submit: ajax_public_application) is executed by the ARQ worker
  at tender open time (status_id == 220), using session stored in Redis.

Security (T-05-20, T-05-21, T-05-22, T-05-23):
- All routes require JWT auth — user_id from current_user.id, NEVER from body (T-05-02).
- Session loaded per-user from Redis by user_id from JWT (T-05-20: no cross-user session use).
- PHPSESSID, CSRF, and encrypted blobs are NEVER logged (T-05-03, T-05-23).
- No direct goszakup XHR from browser — all portal calls via proxy (T-05-21).
- CSRF refreshed from each portal response and re-stored in Redis (T-05-22).
"""

from __future__ import annotations

import logging
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.application import ApplicationResponse
from app.services.application_service import (
    get_user_application,
    mark_ready,
    to_response,
)
from app.services.goszakup_portal_client import GoszakupPortalClient
from app.services.redis_service import (
    get_goszakup_session,
    get_redis,
    store_goszakup_session,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper — load session or 401
# ---------------------------------------------------------------------------


async def _require_session(redis: aioredis.Redis, user_id: int) -> dict:
    """Load goszakup session from Redis.  Raises 401 if not found or expired."""
    session = await get_goszakup_session(redis, user_id)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Сессия goszakup не найдена. Пройдите авторизацию через NCALayer заново.",
        )
    return session


# ===========================================================================
# Request schemas
# ===========================================================================


class LoginRequest(BaseModel):
    signed_xml: str


class CreateDraftRequest(BaseModel):
    tender_buy_id: int
    subject_address: str
    iik: str
    contact_phone: str = ""


class AddLotsRequest(BaseModel):
    application_id: int
    tender_buy_id: int
    lot_ids: list[int]


class LotsNextRequest(BaseModel):
    application_id: int
    tender_buy_id: int


class BeneficiaryRequest(BaseModel):
    app_lot_id: int
    beneficiary_name: str
    beneficiary_doc_number: str
    beneficiary_doc_date: str  # YYYY-MM-DD format


class DocsNextRequest(BaseModel):
    application_id: int
    tender_buy_id: int


class GetEncrInfoRequest(BaseModel):
    application_id: int
    tender_buy_id: int
    lp_id: int
    version: str  # CryptoSocket version string


class AddEncryptRequest(BaseModel):
    application_id: int
    tender_buy_id: int
    item_id: int
    encrypted_data: str
    session_key: str
    salt: str
    info: str
    sign: str


class LotSignData(BaseModel):
    lp_id: int
    xml_data: str
    sign_data: str


class SaveGammaSignsRequest(BaseModel):
    application_id: int
    tender_buy_id: int
    signs: list[LotSignData]


class ProxyLotOffer(BaseModel):
    app_lot_id: int
    lp_id: int
    price: str  # encrypted price blob (encryptData from CryptoSocket)


class PriceoffersNextRequest(BaseModel):
    application_id: int
    tender_buy_id: int
    offers: list[ProxyLotOffer]


class MarkReadyRequest(BaseModel):
    goszakup_application_id: int
    goszakup_tender_buy_id: int


# ===========================================================================
# Endpoints
# ===========================================================================


@router.post("/auth/login")
async def proxy_auth_login(
    body: LoginRequest,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Auth step: NCALayer-signed XML → portal login → store goszakup session in Redis.

    Security: signed_xml proxied to portal, NOT logged (T-05-03).
    """
    client = GoszakupPortalClient()
    phpsessid = await client.login_with_signed_xml(body.signed_xml)

    # Try to get initial CSRF from portal HTML; fallback to empty string
    try:
        csrf = await client.get_initial_csrf(phpsessid)
    except Exception:
        csrf = ""

    await store_goszakup_session(
        redis,
        user_id=current_user.id,
        phpsessid=phpsessid,
        csrf=csrf,
        application_id=0,
        tender_buy_id=0,
    )
    logger.info("proxy_auth_login: session stored for user=%s", current_user.id)
    return {"status": "ok"}


@router.post("/proxy/create-draft")
async def proxy_create_draft(
    body: CreateDraftRequest,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Step 1 proxy: create application draft on goszakup portal.

    Returns {"application_id": <int>}.
    Security: session loaded by user_id from JWT (T-05-20). CSRF not logged (T-05-03).
    """
    session = await _require_session(redis, current_user.id)
    client = GoszakupPortalClient()
    application_id = await client.create_application(
        tender_buy_id=body.tender_buy_id,
        phpsessid=session["phpsessid"],
        csrf=session["csrf"],
        subject_address=body.subject_address,
        iik=body.iik,
        contact_phone=body.contact_phone,
    )
    await store_goszakup_session(
        redis,
        user_id=current_user.id,
        phpsessid=session["phpsessid"],
        csrf=session["csrf"],
        application_id=application_id,
        tender_buy_id=body.tender_buy_id,
    )
    return {"application_id": application_id}


@router.post("/proxy/add-lots")
async def proxy_add_lots(
    body: AddLotsRequest,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Step 2 proxy: add lots to the draft application."""
    session = await _require_session(redis, current_user.id)
    client = GoszakupPortalClient()
    await client.add_lots(
        tender_buy_id=body.tender_buy_id,
        application_id=body.application_id,
        lot_ids=body.lot_ids,
        phpsessid=session["phpsessid"],
        csrf=session["csrf"],
    )
    return {"status": "ok"}


@router.post("/proxy/lots-next")
async def proxy_lots_next(
    body: LotsNextRequest,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Step 3 proxy: confirm lots selection."""
    session = await _require_session(redis, current_user.id)
    client = GoszakupPortalClient()
    await client.lots_next(
        tender_buy_id=body.tender_buy_id,
        application_id=body.application_id,
        phpsessid=session["phpsessid"],
        csrf=session["csrf"],
    )
    return {"status": "ok"}


@router.post("/proxy/beneficiary")
async def proxy_beneficiary(
    body: BeneficiaryRequest,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Step 4 proxy: save beneficiary info for a lot."""
    session = await _require_session(redis, current_user.id)
    client = GoszakupPortalClient()
    await client.save_beneficiary(
        app_lot_id=body.app_lot_id,
        phpsessid=session["phpsessid"],
        csrf=session["csrf"],
        beneficiary_name=body.beneficiary_name,
        beneficiary_doc_number=body.beneficiary_doc_number,
        beneficiary_doc_date=body.beneficiary_doc_date,
    )
    return {"status": "ok"}


@router.post("/proxy/docs-next")
async def proxy_docs_next(
    body: DocsNextRequest,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Step 5 proxy: skip documents step."""
    session = await _require_session(redis, current_user.id)
    client = GoszakupPortalClient()
    await client.docs_next(
        tender_buy_id=body.tender_buy_id,
        application_id=body.application_id,
        phpsessid=session["phpsessid"],
        csrf=session["csrf"],
    )
    return {"status": "ok"}


@router.post("/proxy/get-encr-info")
async def proxy_get_encr_info(
    body: GetEncrInfoRequest,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Step 6 proxy: get encryption params for a lot (public_key, id_priceoffer, etc.).

    Returns the portal JSON response directly to the browser so it can call
    CryptoSocket EFCAPI.EncryptOfferPrice.
    """
    session = await _require_session(redis, current_user.id)
    client = GoszakupPortalClient()
    encr_info = await client.get_encr_info(
        tender_buy_id=body.tender_buy_id,
        application_id=body.application_id,
        lp_id=body.lp_id,
        version=body.version,
        phpsessid=session["phpsessid"],
        csrf=session["csrf"],
    )
    return encr_info


@router.post("/proxy/add-encrypt")
async def proxy_add_encrypt(
    body: AddEncryptRequest,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Step 8 proxy: save CryptoSocket-encrypted price blobs.

    Security: encrypted blobs are NOT logged by the proxy (T-05-23 mitigation).
    """
    session = await _require_session(redis, current_user.id)
    client = GoszakupPortalClient()
    result = await client.add_encrypt(
        tender_buy_id=body.tender_buy_id,
        application_id=body.application_id,
        item_id=body.item_id,
        encrypted_data=body.encrypted_data,
        session_key=body.session_key,
        salt=body.salt,
        info=body.info,
        sign=body.sign,
        phpsessid=session["phpsessid"],
        csrf=session["csrf"],
    )
    return result


@router.post("/proxy/save-gamma-signs")
async def proxy_save_gamma_signs(
    body: SaveGammaSignsRequest,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Step 10 proxy: save NCALayer GOST CMS signatures.

    Security: sign blobs are NOT logged (T-05-23 mitigation).
    """
    session = await _require_session(redis, current_user.id)
    client = GoszakupPortalClient()
    signs_dict: dict[int, tuple[str, str]] = {
        s.lp_id: (s.xml_data, s.sign_data) for s in body.signs
    }
    result = await client.save_gamma_signs(
        tender_buy_id=body.tender_buy_id,
        application_id=body.application_id,
        signs=signs_dict,
        phpsessid=session["phpsessid"],
        csrf=session["csrf"],
    )
    return result


@router.post("/proxy/priceoffers-next")
async def proxy_priceoffers_next(
    body: PriceoffersNextRequest,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """Step 11 proxy: confirm encrypted price offers."""
    session = await _require_session(redis, current_user.id)
    client = GoszakupPortalClient()
    offers_dict: dict[int, dict[int, str]] = {}
    for o in body.offers:
        if o.app_lot_id not in offers_dict:
            offers_dict[o.app_lot_id] = {}
        offers_dict[o.app_lot_id][o.lp_id] = o.price
    await client.priceoffers_next(
        tender_buy_id=body.tender_buy_id,
        application_id=body.application_id,
        offers=offers_dict,
        phpsessid=session["phpsessid"],
        csrf=session["csrf"],
    )
    return {"status": "ok"}


@router.post("/proxy/mark-ready/{app_id}", response_model=ApplicationResponse)
async def proxy_mark_ready(
    app_id: int,
    body: MarkReadyRequest,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """Mark application ready for ARQ submission (draft/signed → waiting).

    Called after wizard steps 1-11 complete successfully.
    1. Verifies ownership via get_user_application (IDOR-safe, T-05-01).
    2. Calls mark_ready to transition state to 'waiting'.
    3. Re-stores Redis session with goszakup_application_id + goszakup_tender_buy_id
       so the ARQ worker can access them for step 12 (T-05-20).
    """
    app = await get_user_application(db, current_user.id, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    session = await _require_session(redis, current_user.id)

    app = await mark_ready(
        db=db,
        app=app,
        goszakup_application_id=body.goszakup_application_id,
        goszakup_tender_buy_id=body.goszakup_tender_buy_id,
    )

    # Re-store session with updated IDs for ARQ worker (T-05-20)
    await store_goszakup_session(
        redis,
        user_id=current_user.id,
        phpsessid=session["phpsessid"],
        csrf=session["csrf"],
        application_id=body.goszakup_application_id,
        tender_buy_id=body.goszakup_tender_buy_id,
    )

    logger.info(
        "proxy_mark_ready: app=%s → waiting, goszakup_app=%s",
        app_id,
        body.goszakup_application_id,
    )
    return to_response(app)
