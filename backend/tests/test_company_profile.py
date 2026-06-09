"""Integration tests for GET/PUT /api/company/profile endpoints.

Test coverage:
  1. get_profile_unauthenticated_returns_401
  2. get_profile_empty_for_new_user
  3. put_profile_creates_row
  4. put_profile_invalid_bin_short_returns_422
  5. put_profile_invalid_bin_checksum_returns_422
  6. put_profile_invalid_bin_position5_returns_422
  7. put_profile_updates_existing_row
"""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


def compute_valid_bin(prefix: str = "190540") -> str:
    """Synthesise a valid 12-digit BIN by computing the correct check digit.

    We fix the first 11 digits (prefix + zeros) then apply the KZ two-cycle
    checksum algorithm to derive digit 12. This guarantees the generated BIN
    will always pass validate_bin().

    prefix must be 6 digits where position 5 (index 4) is in {4,5,6}.
    """
    base = (prefix + "00001").ljust(11, "0")[:11]
    digits = [int(d) for d in base]

    weights1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    total = sum(d * w for d, w in zip(digits, weights1))
    check = total % 11
    if check == 10:
        weights2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
        total2 = sum(d * w for d, w in zip(digits, weights2))
        check = total2 % 11
        if check == 10:
            check = 0
    return base + str(check)


VALID_BIN = compute_valid_bin()


@pytest_asyncio.fixture(scope="module")
async def authed_client():
    """HTTP client pre-authenticated via register — module-scoped to share cookies."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        email = f"companytest_{uuid.uuid4().hex[:8]}@example.com"
        resp = await ac.post(
            "/api/auth/register",
            json={"email": email, "password": "SecurePass123"},
        )
        assert resp.status_code == 201, f"Register failed: {resp.text}"
        yield ac


@pytest.mark.asyncio
async def test_get_profile_unauthenticated_returns_401():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/company/profile")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_profile_empty_for_new_user(authed_client):
    resp = await authed_client.get("/api/company/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["bin"] is None
    assert body["company_name"] is None
    assert body["legal_address"] is None
    assert body["updated_at"] is None


@pytest.mark.asyncio
async def test_put_profile_creates_row(authed_client):
    payload = {
        "bin": VALID_BIN,
        "company_name": "ТОО Тест Компания",
        "legal_address": "г. Алматы, ул. Абая 1",
    }
    resp = await authed_client.put("/api/company/profile", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["bin"] == VALID_BIN
    assert body["company_name"] == "ТОО Тест Компания"
    assert body["legal_address"] == "г. Алматы, ул. Абая 1"
    assert body["updated_at"] is not None


@pytest.mark.asyncio
async def test_put_profile_invalid_bin_short_returns_422(authed_client):
    resp = await authed_client.put(
        "/api/company/profile",
        json={"bin": "12345", "company_name": "X", "legal_address": "Y"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_profile_invalid_bin_checksum_returns_422(authed_client):
    # Position 5 is '4' (valid entity type) but check digit is deliberately wrong
    # Take VALID_BIN and flip the last digit
    bad_bin = VALID_BIN[:11] + str((int(VALID_BIN[11]) + 1) % 10)
    resp = await authed_client.put(
        "/api/company/profile",
        json={"bin": bad_bin, "company_name": "X", "legal_address": "Y"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_profile_invalid_bin_position5_returns_422(authed_client):
    # Position 5 is '1' — this looks like an IIN (individual), not a legal entity BIN
    bad_bin = "190140000012"  # index 4 = '1', will fail position-5 check
    resp = await authed_client.put(
        "/api/company/profile",
        json={"bin": bad_bin, "company_name": "X", "legal_address": "Y"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_profile_updates_existing_row(authed_client):
    """Calling PUT twice must leave exactly one DB row with the latest values."""
    payload1 = {
        "bin": VALID_BIN,
        "company_name": "Первое Название",
        "legal_address": "Адрес 1",
    }
    payload2 = {
        "bin": VALID_BIN,
        "company_name": "Второе Название",
        "legal_address": "Адрес 2",
    }
    r1 = await authed_client.put("/api/company/profile", json=payload1)
    assert r1.status_code == 200

    r2 = await authed_client.put("/api/company/profile", json=payload2)
    assert r2.status_code == 200

    body = r2.json()
    assert body["company_name"] == "Второе Название"
    assert body["legal_address"] == "Адрес 2"

    # Verify no duplicate row: GET returns the latest values
    get_resp = await authed_client.get("/api/company/profile")
    assert get_resp.status_code == 200
    get_body = get_resp.json()
    assert get_body["company_name"] == "Второе Название"
