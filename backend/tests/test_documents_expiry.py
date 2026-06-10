"""TDD RED: Failing tests for compute_expiry_status.

These tests MUST fail before implementation of document_service.py.
"""
import pytest
from datetime import datetime, timezone, timedelta


def test_expiry_status_logic():
    """DOCS-03: compute_expiry_status returns correct status for all boundary dates.

    Covers 5 branches:
    - None → "ok"
    - now + 30 days → "ok"
    - now + 10 days → "warning_14"
    - now + 5 days → "warning_7"
    - now - 1 day → "expired"
    """
    from app.services.document_service import compute_expiry_status

    now = datetime.now(timezone.utc)

    assert compute_expiry_status(None) == "ok"
    assert compute_expiry_status(now + timedelta(days=30)) == "ok"
    assert compute_expiry_status(now + timedelta(days=10)) == "warning_14"
    assert compute_expiry_status(now + timedelta(days=5)) == "warning_7"
    assert compute_expiry_status(now - timedelta(days=1)) == "expired"
