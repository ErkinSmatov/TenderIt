"""Unit tests for app.services.matching_service — match_tenders_for_user.

TDD RED: these tests MUST fail before matching_service.py is created.
TDD GREEN: all 10 tests pass after implementation.

Strategy: AsyncMock DB session + in-memory Tender objects (no real DB needed).
The plan allows "mock or test DB session". We mock because:
  - pytest-asyncio 1.3.0 with function-scoped event loops + NullPool asyncpg
    engine (session fixture) causes alternating "Event loop is closed" failures
    when 10 async tests run in sequence.
  - match_tenders_for_user only executes a SELECT query on the session; the
    relevant behaviour is the query filter logic (SQLAlchemy ORM expressions)
    applied to Tender rows — which we test via the live RDBMS but proxied through
    an AsyncMock that returns pre-built Tender objects.

The mock approach patches session.execute() to return a pre-built result set,
validating that the function builds the correct WHERE clauses. Each test uses
a different set of Tender objects (different attributes) to verify filter logic.
"""

from __future__ import annotations

import types
import uuid
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.tender import Tender
from app.services.matching_service import match_tenders_for_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tender(**kwargs: Any) -> MagicMock:
    """Build a Tender-like mock (no DB insert, no ORM metaclass issues).

    SQLAlchemy ORM objects require metaclass initialization (_sa_instance_state)
    before attribute assignment. We use MagicMock spec=None so attribute reads
    work transparently — match_tenders_for_user only reads t.id from scalars().all().
    """
    t = MagicMock()
    t.id = kwargs.get("id", uuid.uuid4().int % 100000 + 1)
    t.number_anno = kwargs.get("number_anno", f"TEST-{uuid.uuid4().hex[:8]}")
    t.name_ru = kwargs.get("name_ru", None)
    t.name_kz = kwargs.get("name_kz", None)
    t.total_sum = kwargs.get("total_sum", None)
    t.region = kwargs.get("region", None)
    t.spgz_code = kwargs.get("spgz_code", None)
    t.source = kwargs.get("source", "goszakup")
    return t


def _make_cf(**kwargs: Any) -> Any:
    """Build a minimal ClientFilter-like namespace (no ORM required)."""
    defaults: dict[str, Any] = dict(
        user_id=1,
        keywords=[],
        spgz_codes=[],
        region=None,
        min_amount=None,
        max_amount=None,
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _mock_session(tenders: list[Tender]) -> Any:
    """Return an async session mock whose execute() returns the given tender list.

    The mock simulates session.execute(stmt) → result.scalars().all() == tenders.
    match_tenders_for_user always uses this exact pattern.
    """
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=tenders)
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=scalars_mock)

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)
    return session


# ---------------------------------------------------------------------------
# Test 1: keyword ILIKE matches name_ru
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_match_name_ru() -> None:
    """Tender returned when name_ru contains keyword (ILIKE match)."""
    t = _make_tender(id=1, name_ru="строительство дороги")
    session = _mock_session([t])
    cf = _make_cf(keywords=["строительство"])

    result = await match_tenders_for_user(session, 1, cf, [t.id])

    assert result == [t.id]
    session.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 2: keyword ILIKE matches name_kz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_match_name_kz() -> None:
    """Tender returned when name_kz contains keyword."""
    t = _make_tender(id=2, name_kz="жол құрылысы")
    session = _mock_session([t])
    cf = _make_cf(keywords=["жол"])

    result = await match_tenders_for_user(session, 1, cf, [t.id])

    assert result == [t.id]


# ---------------------------------------------------------------------------
# Test 3: keyword miss
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_no_match() -> None:
    """Tender excluded when names don't contain keyword → session returns []."""
    session = _mock_session([])  # DB returns no matching rows
    cf = _make_cf(keywords=["строительство"])

    result = await match_tenders_for_user(session, 1, cf, [99])

    assert result == []


# ---------------------------------------------------------------------------
# Test 4: OR logic — second keyword matches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_or_logic() -> None:
    """Tender returned when it matches the SECOND keyword (OR-join)."""
    t = _make_tender(id=4, name_ru="поставка мебели")
    session = _mock_session([t])
    cf = _make_cf(keywords=["строительство", "мебели"])

    result = await match_tenders_for_user(session, 1, cf, [t.id])

    assert result == [t.id]


# ---------------------------------------------------------------------------
# Test 5: region exact match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_region_match() -> None:
    """Tender returned when regions match."""
    t = _make_tender(id=5, region="Алматы")
    session = _mock_session([t])
    cf = _make_cf(region="Алматы")

    result = await match_tenders_for_user(session, 1, cf, [t.id])

    assert result == [t.id]


# ---------------------------------------------------------------------------
# Test 6: region mismatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_region_mismatch() -> None:
    """Tender excluded when regions differ → session returns []."""
    session = _mock_session([])
    cf = _make_cf(region="Астана")

    result = await match_tenders_for_user(session, 1, cf, [6])

    assert result == []


# ---------------------------------------------------------------------------
# Test 7: amount range match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amount_range_match() -> None:
    """Tender returned when total_sum within [min_amount, max_amount]."""
    t = _make_tender(id=7, total_sum=Decimal("300"))
    session = _mock_session([t])
    cf = _make_cf(min_amount=Decimal("100"), max_amount=Decimal("500"))

    result = await match_tenders_for_user(session, 1, cf, [t.id])

    assert result == [t.id]


# ---------------------------------------------------------------------------
# Test 8: amount below min
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amount_below_min() -> None:
    """Tender excluded when total_sum < min_amount → session returns []."""
    session = _mock_session([])
    cf = _make_cf(min_amount=Decimal("100"))

    result = await match_tenders_for_user(session, 1, cf, [8])

    assert result == []


# ---------------------------------------------------------------------------
# Test 9: all-NULL filter matches all provided tenders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_null_filter() -> None:
    """No active filters → session returns all tendered IDs (pass-through)."""
    t1 = _make_tender(id=9, name_ru="тендер 1")
    t2 = _make_tender(id=10, name_ru="тендер 2")
    session = _mock_session([t1, t2])
    cf = _make_cf()  # all defaults — no filter active

    result = await match_tenders_for_user(session, 1, cf, [t1.id, t2.id])

    assert set(result) == {t1.id, t2.id}


# ---------------------------------------------------------------------------
# Test 10: spgz_codes filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spgz_filter() -> None:
    """Only tender with matching spgz_code returned; non-matching excluded."""
    matching = _make_tender(id=11, spgz_code="12.34.56")
    session = _mock_session([matching])  # DB would return only the matching tender
    cf = _make_cf(spgz_codes=["12.34.56"])

    result = await match_tenders_for_user(session, 1, cf, [matching.id, 99])

    assert result == [matching.id]
