"""Phase 5 — GoszakupPortalClient + Redis session/confirm helpers + proxy router tests.

Group A (05-01): GoszakupPortalClient existing methods + Redis helpers.
Group B (05-03): GoszakupPortalClient steps 1-11 + goszakup_proxy router endpoints.

Acceptance criteria for Group B:
  - Client methods for steps 1-11 exist and post to correct URLs (respx mocks).
  - Proxy endpoint returns 401 when no goszakup_session in Redis.
  - POST /api/goszakup/proxy/create-draft posts to ajax_create_application / returns applicationId.
  - POST /api/goszakup/proxy/mark-ready/{app_id} calls mark_ready and stores application_id +
    tender_buy_id in Redis via store_goszakup_session.
  - goszakup_proxy.py does NOT import or modify main.py.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest
import pytest_asyncio
import respx
from httpx import ASGITransport, AsyncClient, Response

from app.services.goszakup_portal_client import GoszakupPortalClient
from app.services.redis_service import (
    _CONFIRM_TTL,
    _GOSZAKUP_SESSION_TTL,
    get_confirm,
    get_goszakup_session,
    set_confirm_pending,
    store_goszakup_session,
    update_confirm,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PORTAL_BASE = "https://v3bl.goszakup.gov.kz"


@pytest_asyncio.fixture
async def fake_redis():
    """fakeredis async client that mimics aioredis with decode_responses=True."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


# ---------------------------------------------------------------------------
# GoszakupPortalClient — public_application (Step 12)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_public_application_posts_to_correct_url():
    """public_application must POST to /ru/application/ajax_public_application/{buy}/{app}."""
    tender_buy_id = 17269797
    application_id = 71931023
    phpsessid = "test_session_cookie"
    csrf = "test_csrf_token"

    url = (
        f"{PORTAL_BASE}/ru/application/ajax_public_application"
        f"/{tender_buy_id}/{application_id}"
    )
    respx.post(url).mock(return_value=Response(200, json={"status": "ok"}))

    client = GoszakupPortalClient()
    result = await client.public_application(
        tender_buy_id=tender_buy_id,
        application_id=application_id,
        phpsessid=phpsessid,
        csrf=csrf,
    )

    assert result == {"status": "ok"}
    assert respx.calls.last.request.url.path == (
        f"/ru/application/ajax_public_application/{tender_buy_id}/{application_id}"
    )


@pytest.mark.asyncio
@respx.mock
async def test_public_application_sends_public_app_Y():
    """public_application body must contain public_app=Y."""
    tender_buy_id = 17269797
    application_id = 71931023

    url = (
        f"{PORTAL_BASE}/ru/application/ajax_public_application"
        f"/{tender_buy_id}/{application_id}"
    )
    respx.post(url).mock(return_value=Response(200, json={"status": "ok"}))

    client = GoszakupPortalClient()
    await client.public_application(
        tender_buy_id=tender_buy_id,
        application_id=application_id,
        phpsessid="sess",
        csrf="csrf_val",
    )

    # Verify form body
    body = respx.calls.last.request.content.decode()
    assert "public_app=Y" in body
    assert "agree_price=false" in body
    assert "csrf=csrf_val" in body


@pytest.mark.asyncio
@respx.mock
async def test_public_application_returns_dict():
    """public_application must parse JSON response and return dict."""
    tender_buy_id = 99999
    application_id = 11111
    url = (
        f"{PORTAL_BASE}/ru/application/ajax_public_application"
        f"/{tender_buy_id}/{application_id}"
    )
    expected = {"status": "error", "message": "налоговая задолженность"}
    respx.post(url).mock(return_value=Response(200, json=expected))

    client = GoszakupPortalClient()
    result = await client.public_application(tender_buy_id, application_id, "s", "c")
    assert result == expected


@pytest.mark.asyncio
@respx.mock
async def test_login_with_signed_xml_returns_phpsessid():
    """login_with_signed_xml must return the PHPSESSID value from Set-Cookie."""
    signed_xml = "<signed>xml</signed>"
    phpsessid_value = "abc123sessionid"

    url = f"{PORTAL_BASE}/user/sendsign/kz"
    respx.post(url).mock(
        return_value=Response(
            200,
            headers={"Set-Cookie": f"PHPSESSID={phpsessid_value}; Path=/; HttpOnly"},
        )
    )

    client = GoszakupPortalClient()
    result = await client.login_with_signed_xml(signed_xml)
    assert result == phpsessid_value


@pytest.mark.asyncio
@respx.mock
async def test_login_raises_if_no_phpsessid():
    """login_with_signed_xml must raise ValueError when no PHPSESSID in response."""
    url = f"{PORTAL_BASE}/user/sendsign/kz"
    respx.post(url).mock(return_value=Response(200))  # No Set-Cookie

    client = GoszakupPortalClient()
    with pytest.raises(ValueError, match="PHPSESSID"):
        await client.login_with_signed_xml("some_xml")


# ---------------------------------------------------------------------------
# Redis helpers — store/get goszakup_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_and_get_goszakup_session(fake_redis):
    """store_goszakup_session writes JSON; get_goszakup_session returns dict."""
    await store_goszakup_session(
        fake_redis,
        user_id=42,
        phpsessid="sess123",
        csrf="csrf456",
        application_id=71931023,
        tender_buy_id=17269797,
    )

    result = await get_goszakup_session(fake_redis, user_id=42)
    assert result == {
        "phpsessid": "sess123",
        "csrf": "csrf456",
        "application_id": 71931023,
        "tender_buy_id": 17269797,
    }


@pytest.mark.asyncio
async def test_goszakup_session_ttl(fake_redis):
    """store_goszakup_session must apply TTL = _GOSZAKUP_SESSION_TTL (72000s)."""
    await store_goszakup_session(
        fake_redis,
        user_id=1,
        phpsessid="s",
        csrf="c",
        application_id=1,
        tender_buy_id=2,
    )
    ttl = await fake_redis.ttl("goszakup_session:1")
    assert ttl > 0
    assert ttl <= _GOSZAKUP_SESSION_TTL
    # TTL should be close to 72000s (within 5s of set time)
    assert ttl >= _GOSZAKUP_SESSION_TTL - 5


@pytest.mark.asyncio
async def test_get_goszakup_session_returns_none_if_missing(fake_redis):
    """get_goszakup_session returns None when key is absent."""
    result = await get_goszakup_session(fake_redis, user_id=9999)
    assert result is None


# ---------------------------------------------------------------------------
# Redis helpers — confirm key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_confirm_pending_stores_pending(fake_redis):
    """set_confirm_pending writes 'pending' at confirm:{app_id}."""
    await set_confirm_pending(fake_redis, application_id=71931023)
    val = await get_confirm(fake_redis, application_id=71931023)
    assert val == "pending"


@pytest.mark.asyncio
async def test_set_confirm_pending_ttl(fake_redis):
    """set_confirm_pending must apply TTL = _CONFIRM_TTL (900s)."""
    await set_confirm_pending(fake_redis, application_id=12345)
    ttl = await fake_redis.ttl("confirm:12345")
    assert ttl > 0
    assert ttl <= _CONFIRM_TTL
    assert ttl >= _CONFIRM_TTL - 5


@pytest.mark.asyncio
async def test_update_confirm_changes_value(fake_redis):
    """update_confirm changes value to 'yes' or 'no' without resetting TTL."""
    await set_confirm_pending(fake_redis, application_id=99)
    await update_confirm(fake_redis, application_id=99, value="yes")
    val = await get_confirm(fake_redis, application_id=99)
    assert val == "yes"


@pytest.mark.asyncio
async def test_update_confirm_no(fake_redis):
    """update_confirm works with 'no' value."""
    await set_confirm_pending(fake_redis, application_id=88)
    await update_confirm(fake_redis, application_id=88, value="no")
    val = await get_confirm(fake_redis, application_id=88)
    assert val == "no"


@pytest.mark.asyncio
async def test_get_confirm_returns_none_if_missing(fake_redis):
    """get_confirm returns None when key is absent."""
    result = await get_confirm(fake_redis, application_id=77777)
    assert result is None


# ===========================================================================
# Group B (05-03): GoszakupPortalClient steps 1-11
# ===========================================================================

# ---------------------------------------------------------------------------
# Step 1: create_application
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_create_application_posts_to_portal():
    """create_application POSTs to ajax_create_application and returns int applicationId."""
    tender_buy_id = 17269797

    url = f"{PORTAL_BASE}/ru/application/ajax_create_application/{tender_buy_id}"
    respx.post(url).mock(return_value=Response(200, json={"id": 71931023}))

    client = GoszakupPortalClient()
    result = await client.create_application(
        tender_buy_id=tender_buy_id,
        phpsessid="session123",
        csrf="csrf456",
        subject_address="639347",
        iik="000000000001",
    )
    assert result == 71931023
    body = respx.calls.last.request.content.decode()
    assert "csrf=csrf456" in body
    assert "subject_address=639347" in body
    assert "iik=000000000001" in body


# ---------------------------------------------------------------------------
# Step 2: add_lots
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_add_lots_posts_to_portal():
    """add_lots POSTs selectLots[] to ajax_add_lots/{buy_id}/{app_id}."""
    tender_buy_id = 17269797
    application_id = 71931023

    url = f"{PORTAL_BASE}/ru/application/ajax_add_lots/{tender_buy_id}/{application_id}"
    respx.post(url).mock(return_value=Response(200, text="OK"))

    client = GoszakupPortalClient()
    await client.add_lots(
        tender_buy_id=tender_buy_id,
        application_id=application_id,
        lot_ids=[42460233],
        phpsessid="s",
        csrf="c",
    )
    body = respx.calls.last.request.content.decode()
    assert "42460233" in body
    assert "selectLots" in body


# ---------------------------------------------------------------------------
# Step 3: lots_next
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_lots_next_posts_to_portal():
    """lots_next POSTs next=1&confirmed=0 to ajax_lots_next."""
    tender_buy_id = 17269797
    application_id = 71931023

    url = f"{PORTAL_BASE}/ru/application/ajax_lots_next/{tender_buy_id}/{application_id}"
    respx.post(url).mock(return_value=Response(200, text="OK"))

    client = GoszakupPortalClient()
    await client.lots_next(
        tender_buy_id=tender_buy_id,
        application_id=application_id,
        phpsessid="s",
        csrf="c",
    )
    body = respx.calls.last.request.content.decode()
    assert "next=1" in body
    assert "confirmed=0" in body


# ---------------------------------------------------------------------------
# Step 4: save_beneficiary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_save_beneficiary_posts_to_portal():
    """save_beneficiary POSTs to /ru/beneficiary/ajax_save_info with required fields."""
    url = f"{PORTAL_BASE}/ru/beneficiary/ajax_save_info"
    respx.post(url).mock(return_value=Response(200, json={"status": "ok"}))

    client = GoszakupPortalClient()
    await client.save_beneficiary(
        app_lot_id=86257005,
        phpsessid="s",
        csrf="c",
        beneficiary_name="Иванов Иван",
        beneficiary_doc_number="123456789",
        beneficiary_doc_date="2026-07-01",
    )
    body = respx.calls.last.request.content.decode()
    assert "app_lot_id=86257005" in body
    assert "citizenship=398" in body
    assert "option_1=1" in body
    assert "option_4=2" in body


# ---------------------------------------------------------------------------
# Step 5: docs_next
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_docs_next_posts_to_portal():
    """docs_next POSTs next=1 to ajax_docs_next."""
    tender_buy_id = 17269797
    application_id = 71931023

    url = f"{PORTAL_BASE}/ru/application/ajax_docs_next/{tender_buy_id}/{application_id}"
    respx.post(url).mock(return_value=Response(200, text="OK"))

    client = GoszakupPortalClient()
    await client.docs_next(
        tender_buy_id=tender_buy_id,
        application_id=application_id,
        phpsessid="s",
        csrf="c",
    )
    body = respx.calls.last.request.content.decode()
    assert "next=1" in body


# ---------------------------------------------------------------------------
# Step 6: get_encr_info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_encr_info_returns_json():
    """get_encr_info POSTs lpId+version to ajax_get_encr_info and returns JSON."""
    tender_buy_id = 17269797
    application_id = 71931023
    lp_id = 41914081

    url = f"{PORTAL_BASE}/ru/application/ajax_get_encr_info/{tender_buy_id}/{application_id}"
    encr_data = {"public_key": "BQIAAEU...", "id_priceoffer": "AF89UX3146"}
    respx.post(url).mock(return_value=Response(200, json=encr_data))

    client = GoszakupPortalClient()
    result = await client.get_encr_info(
        tender_buy_id=tender_buy_id,
        application_id=application_id,
        lp_id=lp_id,
        version="1.0.0",
        phpsessid="s",
        csrf="c",
    )
    assert result == encr_data
    body = respx.calls.last.request.content.decode()
    assert f"lpId={lp_id}" in body


# ---------------------------------------------------------------------------
# Step 8: add_encrypt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_add_encrypt_posts_to_portal():
    """add_encrypt POSTs encrypted fields to ajax_add_encrypt."""
    tender_buy_id = 17269797
    application_id = 71931023

    url = f"{PORTAL_BASE}/ru/application/ajax_add_encrypt/{tender_buy_id}/{application_id}"
    respx.post(url).mock(return_value=Response(200, json={"status": "ok"}))

    client = GoszakupPortalClient()
    result = await client.add_encrypt(
        tender_buy_id=tender_buy_id,
        application_id=application_id,
        item_id=41914081,
        encrypted_data="bR41xz",
        session_key="sk_val",
        salt="salt_val",
        info="info_val",
        sign="sign_val",
        phpsessid="s",
        csrf="c",
    )
    assert result == {"status": "ok"}
    body = respx.calls.last.request.content.decode()
    assert "itemID=41914081" in body
    assert "encryptedData=bR41xz" in body
    assert "sessionKey=sk_val" in body


# ---------------------------------------------------------------------------
# Step 10: save_gamma_signs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_save_gamma_signs_posts_to_portal():
    """save_gamma_signs POSTs xmlData[lpId]+signData[lpId] to ajax_save_gamma_signs."""
    tender_buy_id = 17269797
    application_id = 71931023
    lp_id = 41914081

    url = f"{PORTAL_BASE}/ru/application/ajax_save_gamma_signs/{tender_buy_id}/{application_id}"
    respx.post(url).mock(return_value=Response(200, json={"status": "ok"}))

    client = GoszakupPortalClient()
    result = await client.save_gamma_signs(
        tender_buy_id=tender_buy_id,
        application_id=application_id,
        signs={lp_id: ("bR41xz", "MIIP8gYJ")},
        phpsessid="s",
        csrf="c",
    )
    assert result == {"status": "ok"}
    body = respx.calls.last.request.content.decode()
    assert "xmlData" in body
    assert "signData" in body
    assert str(lp_id) in body


# ---------------------------------------------------------------------------
# Step 11: priceoffers_next
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_priceoffers_next_posts_to_portal():
    """priceoffers_next POSTs offer[app_lot_id][lp_id][price] to ajax_priceoffers_next."""
    tender_buy_id = 17269797
    application_id = 71931023

    url = f"{PORTAL_BASE}/ru/application/ajax_priceoffers_next/{tender_buy_id}/{application_id}"
    respx.post(url).mock(return_value=Response(200, text="OK"))

    client = GoszakupPortalClient()
    await client.priceoffers_next(
        tender_buy_id=tender_buy_id,
        application_id=application_id,
        offers={86257005: {41914081: "bR41xz"}},
        phpsessid="s",
        csrf="c",
    )
    body = respx.calls.last.request.content.decode()
    assert "offer" in body
    assert "86257005" in body
    assert "41914081" in body


# ===========================================================================
# Group B: goszakup_proxy router endpoint tests
# ===========================================================================

from app.main import app as fastapi_app
from app.services.redis_service import get_redis as get_redis_dep


async def _register_and_login_proxy(prefix: str = "proxtest") -> AsyncClient:
    """Create a fresh AsyncClient authenticated as a new unique user (for proxy tests)."""
    ac = AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test")
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    with patch("app.routers.auth.store_refresh_token", new=AsyncMock()):
        resp = await ac.post(
            "/api/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    return ac


@pytest_asyncio.fixture
async def authed_proxy():
    """Function-scoped authenticated client for proxy route tests."""
    ac = await _register_and_login_proxy()
    yield ac
    await ac.aclose()


@pytest_asyncio.fixture
async def redis_for_proxy():
    """Fresh fakeredis instance injected as get_redis dependency for proxy tests."""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def _override():
        yield fake

    fastapi_app.dependency_overrides[get_redis_dep] = _override
    yield fake
    fastapi_app.dependency_overrides.pop(get_redis_dep, None)
    await fake.aclose()


# ---------------------------------------------------------------------------
# Proxy: 401 without session (T-05-20)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proxy_create_draft_401_without_session(authed_proxy, redis_for_proxy):
    """POST /api/goszakup/proxy/create-draft returns 401 when no goszakup_session in Redis."""
    resp = await authed_proxy.post(
        "/api/goszakup/proxy/create-draft",
        json={
            "tender_buy_id": 17269797,
            "subject_address": "639347",
            "iik": "000000000001",
        },
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Proxy: create-draft posts to portal and returns applicationId
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_proxy_create_draft_returns_application_id(authed_proxy, redis_for_proxy):
    """POST /api/goszakup/proxy/create-draft posts to ajax_create_application and returns applicationId."""
    tender_buy_id = 17269797
    application_id = 71931023

    portal_url = f"{PORTAL_BASE}/ru/application/ajax_create_application/{tender_buy_id}"
    respx.post(portal_url).mock(return_value=Response(200, json={"id": application_id}))

    with patch(
        "app.routers.goszakup_proxy.get_goszakup_session",
        new=AsyncMock(return_value={
            "phpsessid": "sess123",
            "csrf": "csrf456",
            "application_id": 0,
            "tender_buy_id": tender_buy_id,
        }),
    ), patch(
        "app.routers.goszakup_proxy.store_goszakup_session",
        new=AsyncMock(),
    ):
        resp = await authed_proxy.post(
            "/api/goszakup/proxy/create-draft",
            json={
                "tender_buy_id": tender_buy_id,
                "subject_address": "639347",
                "iik": "000000000001",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["application_id"] == application_id


# ---------------------------------------------------------------------------
# Proxy: mark-ready calls mark_ready and stores session with application_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_proxy_mark_ready_calls_mark_ready_and_stores_session(
    authed_proxy, redis_for_proxy
):
    """POST /api/goszakup/proxy/mark-ready/{app_id} transitions app to waiting and stores session."""
    from app.services.goszakup_service import GRAPHQL_URL
    import httpx as _httpx

    gz_tender = {
        "id": 17269797,
        "numberAnno": "17269797-1",
        "nameRu": "Тест",
        "nameKz": None,
        "totalSum": 500000,
        "countLots": 1,
        "customerBin": "000000000001",
        "customerNameRu": "Заказчик",
        "customerNameKz": None,
        "refBuyStatusId": 220,
        "RefBuyStatus": {
            "id": 220,
            "nameRu": "Опубликовано",
            "nameKz": None,
            "code": "PublishedOrderTaking",
        },
        "startDate": "2026-07-01 10:00:00",
        "endDate": "2026-07-15 10:00:00",
        "publishDate": "2026-07-01 09:00:00",
        "lastUpdateDate": "2026-07-01 09:00:00",
        "Lots": [
            {
                "id": 42460233,
                "lotNumber": "1",
                "nameRu": "Лот",
                "nameKz": None,
                "descriptionRu": "Desc",
                "amount": 500000,
                "refLotStatusId": 220,
            }
        ],
    }
    respx.post(GRAPHQL_URL).mock(
        return_value=_httpx.Response(200, json={"data": {"TrdBuy": [gz_tender]}})
    )
    await authed_proxy.get("/api/tenders/17269797-1")

    # Fetch tender DB id
    from sqlalchemy import select
    import app.db as db_module
    from app.models.tender import Tender as TenderModel

    async with db_module.AsyncSessionLocal() as session:
        result = await session.execute(
            select(TenderModel).where(TenderModel.number_anno == "17269797-1")
        )
        tender_db = result.scalar_one_or_none()
    assert tender_db is not None, "Tender must be in DB for mark-ready test"

    # Create draft application
    create_resp = await authed_proxy.post(
        "/api/applications",
        json={
            "tender_id": tender_db.id,
            "lots_data": [
                {
                    "lot_id": 42460233,
                    "unit_price": "100.00",
                    "quantity": 5,
                    "total_price": "500.00",
                }
            ],
            "document_ids": [],
        },
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    goszakup_app_id = 71931023
    goszakup_buy_id = 17269797

    with patch(
        "app.routers.goszakup_proxy.get_goszakup_session",
        new=AsyncMock(return_value={
            "phpsessid": "sess123",
            "csrf": "csrf456",
            "application_id": 0,
            "tender_buy_id": goszakup_buy_id,
        }),
    ), patch(
        "app.routers.goszakup_proxy.store_goszakup_session",
        new=AsyncMock(),
    ) as mock_store:
        resp = await authed_proxy.post(
            f"/api/goszakup/proxy/mark-ready/{app_id}",
            json={
                "goszakup_application_id": goszakup_app_id,
                "goszakup_tender_buy_id": goszakup_buy_id,
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "waiting"
    assert body["goszakup_application_id"] == goszakup_app_id

    # Verify store_goszakup_session was called and included application_id
    mock_store.assert_called_once()
    call_kwargs = mock_store.call_args.kwargs
    call_args = mock_store.call_args.args
    assert (
        call_kwargs.get("application_id") == goszakup_app_id
        or goszakup_app_id in call_args
    )
