"""Unit tests for app.services.matching_service — match_tenders_for_user.

TDD RED: these tests MUST fail before matching_service.py is created.
TDD GREEN: all 10 tests pass after implementation.

Uses the real test DB (db_session fixture from conftest.py) to insert Tender rows
and validate that the ILIKE / region / spgz_code / amount filters work correctly.

The ClientFilter is constructed in-memory (no DB insert needed) since
match_tenders_for_user only reads cf.keywords, cf.region, etc. from the object.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest

from app.models.client_filter import ClientFilter
from app.models.tender import Tender
from app.services.matching_service import match_tenders_for_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_anno() -> str:
    """Generate a unique number_anno for test tenders."""
    return f"TEST-MATCH-{uuid.uuid4().hex[:10]}"


def _make_cf(**kwargs: Any) -> ClientFilter:
    """Build an in-memory ClientFilter with safe defaults.

    No DB insert — match_tenders_for_user only reads attributes.
    """
    cf = ClientFilter.__new__(ClientFilter)
    cf.id = kwargs.get("id", 0)
    cf.user_id = kwargs.get("user_id", 1)
    cf.keywords = kwargs.get("keywords", [])
    cf.spgz_codes = kwargs.get("spgz_codes", [])
    cf.region = kwargs.get("region", None)
    cf.min_amount = kwargs.get("min_amount", None)
    cf.max_amount = kwargs.get("max_amount", None)
    return cf


async def _insert_tender(db_session: Any, **kwargs: Any) -> Tender:
    """Insert a Tender row within the test transaction and return the ORM object."""
    defaults: dict[str, Any] = dict(
        number_anno=_unique_anno(),
        name_ru=None,
        name_kz=None,
        source="goszakup",
        region=None,
        spgz_code=None,
        total_sum=None,
    )
    defaults.update(kwargs)
    tender = Tender(**defaults)
    db_session.add(tender)
    await db_session.flush()
    return tender


# ---------------------------------------------------------------------------
# Test 1: keyword ILIKE matches name_ru
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_match_name_ru(db_session: Any) -> None:
    """Tender with name_ru containing keyword is returned (ILIKE, case-insensitive)."""
    tender = await _insert_tender(db_session, name_ru="строительство дороги")
    cf = _make_cf(keywords=["строительство"])

    result = await match_tenders_for_user(db_session, cf.user_id, cf, [tender.id])

    assert result == [tender.id]


# ---------------------------------------------------------------------------
# Test 2: keyword ILIKE matches name_kz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_match_name_kz(db_session: Any) -> None:
    """Tender with name_kz containing keyword is returned."""
    tender = await _insert_tender(db_session, name_kz="жол құрылысы")
    cf = _make_cf(keywords=["жол"])

    result = await match_tenders_for_user(db_session, cf.user_id, cf, [tender.id])

    assert result == [tender.id]


# ---------------------------------------------------------------------------
# Test 3: keyword miss
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_no_match(db_session: Any) -> None:
    """Tender whose names don't contain any keyword is excluded."""
    tender = await _insert_tender(db_session, name_ru="поставка мебели")
    cf = _make_cf(keywords=["строительство"])

    result = await match_tenders_for_user(db_session, cf.user_id, cf, [tender.id])

    assert result == []


# ---------------------------------------------------------------------------
# Test 4: OR logic — second keyword matches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_or_logic(db_session: Any) -> None:
    """Tender is returned when it matches the SECOND keyword (OR-join logic)."""
    tender = await _insert_tender(db_session, name_ru="поставка мебели")
    cf = _make_cf(keywords=["строительство", "мебели"])

    result = await match_tenders_for_user(db_session, cf.user_id, cf, [tender.id])

    assert result == [tender.id]


# ---------------------------------------------------------------------------
# Test 5: region exact match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_region_match(db_session: Any) -> None:
    """Tender with matching region is returned."""
    tender = await _insert_tender(db_session, region="Алматы")
    cf = _make_cf(region="Алматы")

    result = await match_tenders_for_user(db_session, cf.user_id, cf, [tender.id])

    assert result == [tender.id]


# ---------------------------------------------------------------------------
# Test 6: region mismatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_region_mismatch(db_session: Any) -> None:
    """Tender with a different region is excluded (exact match)."""
    tender = await _insert_tender(db_session, region="Алматы")
    cf = _make_cf(region="Астана")

    result = await match_tenders_for_user(db_session, cf.user_id, cf, [tender.id])

    assert result == []


# ---------------------------------------------------------------------------
# Test 7: amount range match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amount_range_match(db_session: Any) -> None:
    """Tender within [min_amount, max_amount] is returned."""
    tender = await _insert_tender(db_session, total_sum=Decimal("300"))
    cf = _make_cf(min_amount=Decimal("100"), max_amount=Decimal("500"))

    result = await match_tenders_for_user(db_session, cf.user_id, cf, [tender.id])

    assert result == [tender.id]


# ---------------------------------------------------------------------------
# Test 8: amount below min
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amount_below_min(db_session: Any) -> None:
    """Tender below cf.min_amount is excluded."""
    tender = await _insert_tender(db_session, total_sum=Decimal("50"))
    cf = _make_cf(min_amount=Decimal("100"))

    result = await match_tenders_for_user(db_session, cf.user_id, cf, [tender.id])

    assert result == []


# ---------------------------------------------------------------------------
# Test 9: all-NULL filter matches all provided tenders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_null_filter(db_session: Any) -> None:
    """Empty keywords / None region / None amounts = no filter → all tenders returned."""
    tender1 = await _insert_tender(db_session, name_ru="тендер 1")
    tender2 = await _insert_tender(db_session, name_ru="тендер 2")
    cf = _make_cf()  # all defaults → no active filter

    result = await match_tenders_for_user(
        db_session, cf.user_id, cf, [tender1.id, tender2.id]
    )

    assert set(result) == {tender1.id, tender2.id}


# ---------------------------------------------------------------------------
# Test 10: spgz_codes filter — exact match on tender.spgz_code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spgz_filter(db_session: Any) -> None:
    """Tender with matching spgz_code is returned; non-matching is excluded."""
    matching = await _insert_tender(db_session, spgz_code="12.34.56")
    no_match = await _insert_tender(db_session, spgz_code="99.99.99")
    cf = _make_cf(spgz_codes=["12.34.56"])

    result = await match_tenders_for_user(
        db_session, cf.user_id, cf, [matching.id, no_match.id]
    )

    assert result == [matching.id]
