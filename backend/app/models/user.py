from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import BigInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Phase 5 (D-05-06): Telegram chat ID for submission notification flow
    telegram_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # Phase 6 (D-09): Telegram deep-link token for account linking flow (NOTIF-04)
    telegram_link_token: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    telegram_link_token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )

    company_profile: Mapped[Optional["CompanyProfile"]] = relationship("CompanyProfile", back_populates="user", lazy="selectin", uselist=False)
