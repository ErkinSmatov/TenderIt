"""ClientFilter ORM model.

Stores a user's tender discovery filter set.

Per D-10 (07-CONTEXT.md): one filter set per user (UNIQUE(user_id) enforced by migration 0006).
Upsert semantics — PUT replaces the entire record.

No relationships needed — ClientFilter is used as a data record, not navigated via ORM.

DDL source: .planning/phases/07-discovery-matching/07-01-PLAN.md, Task 1.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ClientFilter(Base):
    __tablename__ = "client_filters"

    id: Mapped[int] = mapped_column(primary_key=True)

    # user_id — ALWAYS from JWT (get_current_user dep), NEVER from request body
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Keyword list — OR-joined ILIKE against tender name_ru / name_kz
    # Max 20 items enforced at schema level (T-07-04 DoS guard in ClientFilterCreate)
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )

    # СПГЗ codes — exact match on tender.spgz_code
    spgz_codes: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )

    # Region — exact match on tender.region; NULL = no region filter
    region: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Amount range — both nullable; NULL = no bound applied
    min_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    max_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
