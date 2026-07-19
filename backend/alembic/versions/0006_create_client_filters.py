"""create_client_filters

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-19

Creates client_filters table for Phase 7 Discovery & Matching.

Per D-10 (07-CONTEXT.md): UNIQUE(user_id) — one filter set per user (upsert semantics).
v1 has no named presets or multiple filter sets.

Columns:
  id          — SERIAL PK
  user_id     — FK → users(id) ON DELETE CASCADE (T-07-schema-02 mitigation)
  keywords    — TEXT[] NOT NULL DEFAULT '{}' — matched via ILIKE against tender name
  spgz_codes  — TEXT[] NOT NULL DEFAULT '{}' — exact-match on tender.spgz_code
  region      — TEXT nullable — exact-match on tender.region
  min_amount  — NUMERIC(18,2) nullable — lower bound on tender.total_sum
  max_amount  — NUMERIC(18,2) nullable — upper bound on tender.total_sum
  created_at  — TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at  — TIMESTAMPTZ NOT NULL DEFAULT now()
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_filters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # Keyword list — OR-joined ILIKE against tender name_ru / name_kz
        sa.Column(
            "keywords",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        # СПГЗ codes — exact match on tender.spgz_code
        sa.Column(
            "spgz_codes",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        # Region — exact match on tender.region; NULL = no region filter
        sa.Column("region", sa.Text(), nullable=True),
        # Amount range — both nullable; NULL = no bound
        sa.Column("min_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("max_amount", sa.Numeric(18, 2), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # D-10: one filter set per user — upsert replaces the entire record
    op.create_unique_constraint(
        "uq_client_filters_user_id",
        "client_filters",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("client_filters")
