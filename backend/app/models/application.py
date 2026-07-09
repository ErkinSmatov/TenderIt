"""Application ORM model.

State machine for a tender application submitted through the TenderIt platform.
Status is stored as TEXT (not PG ENUM) for easy v2 extension — D-05-04 decision.

Valid status values: draft | signed | waiting | submitting | submitted | error

Session data (PHPSESSID, CSRF) is stored in Redis (goszakup_session:{user_id}),
NOT in PostgreSQL — sessions have short TTLs and change frequently (D-05-02 decision).

DDL source: .planning/phases/05-eds-signing-submission/05-CONTEXT.md, D-05-04.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)

    # user_id — ALWAYS from JWT (get_current_user dep), NEVER from request body (T-05-02)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Draft data — lots offers entered by user, stored in TenderIt (not on goszakup)
    # Structure: [{lotId, unitPrice, quantity, totalPrice}]
    lots_data: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)

    # References to documents.id (user selects from Document Vault in Phase 5 wizard)
    document_ids: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),
        nullable=False,
        server_default="{}",
    )

    # goszakup portal IDs — filled after browser completes wizard steps 1-11
    goszakup_application_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )
    goszakup_tender_buy_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )

    # State machine — TEXT not PG ENUM (D-05-04 decision: easy v2 extension)
    # Values: draft | signed | waiting | submitting | submitted | error
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="draft"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    # ready_at: set when browser finishes steps 1-11 (replaces signed_at — D-05-04)
    ready_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
