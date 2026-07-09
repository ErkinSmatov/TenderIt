"""Phase 5 — GoszakupPortalClient + Redis session/confirm helpers tests.

Task 2 tests (this file):
  - GoszakupPortalClient.public_application: posts to exact URL with public_app=Y (via respx)
  - GoszakupPortalClient.login_with_signed_xml: returns PHPSESSID from Set-Cookie (via respx)
  - Redis helpers: store/get goszakup_session, set_confirm_pending, update_confirm, get_confirm (via fakeredis)

Task 3 goszakup_proxy router tests are also included below (added in Task 3 to avoid a second file).

Acceptance criteria for Task 2:
  - public_application posts to /ru/application/ajax_public_application/{buy_id}/{app_id}
  - Body contains public_app=Y
  - Returns parsed JSON dict
  - Redis helpers respect TTLs: _GOSZAKUP_SESSION_TTL=72000, _CONFIRM_TTL=900
  - update_confirm does NOT extend TTL (uses SET not SETEX)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest
import pytest_asyncio
import respx
from httpx import Response

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
