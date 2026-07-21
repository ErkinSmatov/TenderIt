"""add_telegram_link_token

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-21

Adds Telegram deep-link token fields to users table for Phase 6 account linking (NOTIF-04).

Columns added to users:
  telegram_link_token          — String(64) nullable, unique — 43-char URL-safe token
  telegram_link_token_expires_at — TIMESTAMPTZ nullable — 15-min expiry enforced in app layer

Index:
  idx_users_telegram_link_token — UNIQUE on telegram_link_token — dedup + fast lookup

Security:
  T-06-01: token generated with secrets.token_urlsafe(32) = 256-bit entropy in app layer.
  T-06-02: token cleared on first successful /start use — cannot be replayed.
  T-06-05: expires_at checked with timezone-aware datetime.now(timezone.utc) — no naive comparison.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("telegram_link_token", sa.String(64), nullable=True),
    )
    op.create_index(
        "idx_users_telegram_link_token",
        "users",
        ["telegram_link_token"],
        unique=True,
    )
    op.add_column(
        "users",
        sa.Column(
            "telegram_link_token_expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "telegram_link_token_expires_at")
    op.drop_index("idx_users_telegram_link_token", table_name="users")
    op.drop_column("users", "telegram_link_token")
