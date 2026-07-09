from __future__ import annotations

from datetime import datetime
from typing import Optional

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

    company_profile: Mapped[Optional["CompanyProfile"]] = relationship("CompanyProfile", back_populates="user", lazy="selectin", uselist=False)
