"""Unit tests for create_discovery_draft in application_service.py.

Tests (DISC-05):
  1. test_create_discovery_draft_status: result.status == 'draft'
  2. test_create_discovery_draft_lots_empty: result.lots_data == [] (bypasses validator)
  3. test_create_discovery_draft_tender_id: result.tender_id == provided value
  4. test_create_discovery_draft_user_id: result.user_id == provided value
  5. test_application_create_validator_rejects_empty_lots: REGRESSION GUARD — validator still active

Uses AsyncMock for the DB session because create_discovery_draft commits internally,
which is incompatible with the rollback-based db_session fixture.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.schemas.application import ApplicationCreate
from app.services.application_service import create_discovery_draft


# ---------------------------------------------------------------------------
# create_discovery_draft unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_discovery_draft_status():
    """create_discovery_draft creates Application with status='draft' (DISC-05)."""
    mock_db = AsyncMock()
    result = await create_discovery_draft(mock_db, user_id=1, tender_id=5)
    assert result.status == "draft"


@pytest.mark.asyncio
async def test_create_discovery_draft_lots_empty():
    """create_discovery_draft sets lots_data=[] — bypasses lots_data_must_be_non_empty validator."""
    mock_db = AsyncMock()
    result = await create_discovery_draft(mock_db, user_id=1, tender_id=5)
    assert result.lots_data == []


@pytest.mark.asyncio
async def test_create_discovery_draft_tender_id():
    """create_discovery_draft assigns the provided tender_id."""
    mock_db = AsyncMock()
    result = await create_discovery_draft(mock_db, user_id=1, tender_id=42)
    assert result.tender_id == 42


@pytest.mark.asyncio
async def test_create_discovery_draft_user_id():
    """create_discovery_draft assigns the provided user_id."""
    mock_db = AsyncMock()
    result = await create_discovery_draft(mock_db, user_id=7, tender_id=5)
    assert result.user_id == 7


# ---------------------------------------------------------------------------
# REGRESSION GUARD — ApplicationCreate validator must remain active
# ---------------------------------------------------------------------------


def test_application_create_validator_rejects_empty_lots():
    """REGRESSION GUARD: ApplicationCreate still raises ValidationError for empty lots_data.

    create_discovery_draft bypasses this schema intentionally (D-05 / pitfall 1).
    This test guards against accidentally removing the validator from ApplicationCreate.
    If this test fails, the validation that protects the HTTP API layer has been removed.
    """
    with pytest.raises(ValidationError):
        ApplicationCreate(tender_id=1, lots_data=[])
