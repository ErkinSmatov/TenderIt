"""TenderMatch ORM model.

Records the result of matching a tender against a user's ClientFilter.

Per D-11 (07-CONTEXT.md): status machine: matched → notified → (skipped | participating).
Per D-02: NO profitability column — formula undefined, deferred to v2.
Per T-07-schema-01: UNIQUE(user_id, tender_id) enforced by migration 0007.

No eager relationships (lazy="noload" matches Tender/Application pattern).

DDL source: .planning/phases/07-discovery-matching/07-01-PLAN.md, Task 1.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TenderMatch(Base):
    __tablename__ = "tender_matches"

    id: Mapped[int] = mapped_column(primary_key=True)

    # user_id — ALWAYS from JWT (get_current_user dep), NEVER from request body
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
    )

    # State machine — TEXT not PG ENUM for easy v2 extension (same pattern as Application)
    # Valid values: matched | notified | skipped | participating
    # matched     — run_matching created this record
    # notified    — Telegram message sent to user
    # skipped     — user pressed "Пропустить" (disc:skip:{match_id})
    # participating — user pressed "Участвуем" (disc:participate:{match_id})
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="matched"
    )

    # Timestamps for notification and decision events
    notified_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Standard audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
