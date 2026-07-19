"""Tender and UserWatchlist ORM models.

DDL source: .planning/phases/03-tender-lookup/03-CONTEXT.md, Decision 1.
Date format note (SPIKE-01, 2026-06-10): goszakup returns "YYYY-MM-DD HH:MM:SS"
  (no tz suffix) — tender_service parses and attaches UTC+5 before storing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(primary_key=True)
    # numberAnno from goszakup: format "{trd_buy_id}-{version}", e.g. "17163708-1"
    number_anno: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    name_ru: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    name_kz: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_sum: Mapped[Optional[Any]] = mapped_column(Numeric(18, 2), nullable=True)
    customer_name_ru: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    customer_name_kz: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # refBuyStatusId: 220 = "Опубликовано (прием заявок)" / PublishedOrderTaking
    status_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status_name_ru: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    publish_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Lots array from TrdBuy GraphQL query stored as JSONB
    lots_data: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    # Full raw TrdBuy dict for auditability and future field access
    raw_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    # Cache TTL anchor — 30-min window enforced by tender_service.get_or_fetch_tender
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Phase 7 Discovery & Matching — added by migration 0005
    # source: which platform published the tender (only 'goszakup' in v1; D-01 locks sk.kz to v2)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="goszakup")
    # region: matches client_filters.region (exact match); NULL = region unknown
    region: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # spgz_code: СПГЗ classifier code from goszakup Lots; NULL until goszakup field name confirmed
    # See 07-RESEARCH.md Pitfall 7 — field name verified by 07-02 introspection query
    spgz_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    watchlist_entries: Mapped[list["UserWatchlist"]] = relationship(
        "UserWatchlist", back_populates="tender", lazy="noload"
    )


class UserWatchlist(Base):
    __tablename__ = "user_watchlist"
    __table_args__ = (
        UniqueConstraint("user_id", "tender_id", name="uq_user_watchlist"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    notification_on: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    tender: Mapped["Tender"] = relationship(
        "Tender", back_populates="watchlist_entries", lazy="noload"
    )
