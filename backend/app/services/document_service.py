"""Document service — pure utility and async CRUD functions.

compute_expiry_status: pure function, no DB/MinIO access.
  Uses datetime.now(timezone.utc) — tz-aware comparison (Pitfall 7 mitigation, T-04-07).
  Must NOT use datetime.now() without timezone — would fail with TypeError in Python 3.12
  when comparing naive datetime with tz-aware datetime from TIMESTAMPTZ column.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

ExpiryStatus = Literal["ok", "warning_14", "warning_7", "expired"]


def compute_expiry_status(expires_at: datetime | None) -> ExpiryStatus:
    """Compute document expiry status relative to current UTC time.

    Branches:
      None       → "ok"   (permanent document, no expiry date)
      days > 14  → "ok"
      8 ≤ days ≤ 14 → "warning_14"
      1 ≤ days ≤ 7  → "warning_7"
      days < 0   → "expired"

    Security note (T-04-07): uses datetime.now(timezone.utc) — tz-aware.
    Cannot compare tz-naive with tz-aware in Python 3.12+ (TypeError).
    TIMESTAMPTZ columns from PostgreSQL always return tz-aware datetime via asyncpg.
    """
    if expires_at is None:
        return "ok"
    now = datetime.now(timezone.utc)
    delta = expires_at - now
    days = delta.days
    if days < 0:
        return "expired"
    if days <= 7:
        return "warning_7"
    if days <= 14:
        return "warning_14"
    return "ok"
