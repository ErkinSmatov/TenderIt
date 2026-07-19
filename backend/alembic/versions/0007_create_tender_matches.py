"""create_tender_matches

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-19

Creates tender_matches table for Phase 7 Discovery & Matching.

Per D-11 (07-CONTEXT.md): status machine: matched → notified → (skipped | participating).
Per D-02: NO profitability column — formula undefined, deferred to v2.
Per T-07-schema-01: UNIQUE(user_id, tender_id) prevents duplicate matches under concurrent ARQ runs.

Columns:
  id           — SERIAL PK
  user_id      — FK → users(id) ON DELETE CASCADE
  tender_id    — FK → tenders(id) ON DELETE CASCADE
  status       — TEXT NOT NULL DEFAULT 'matched'
                 Values: matched | notified | skipped | participating
  notified_at  — TIMESTAMPTZ nullable — set when Telegram message sent
  decided_at   — TIMESTAMPTZ nullable — set when user clicks Участвуем or Пропустить
  created_at   — TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at   — TIMESTAMPTZ NOT NULL DEFAULT now()

Indexes:
  uq_tender_matches_user_tender  — UNIQUE(user_id, tender_id) — dedup + fast lookup
  idx_tender_matches_user_id     — for GET /api/discovery/matches (list by user)
  idx_tender_matches_status      — for run_matching worker query on unnotified matches
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tender_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tender_id", sa.Integer(), nullable=False),
        # State machine — TEXT not PG ENUM for easy v2 extension (same pattern as applications)
        # Values: matched | notified | skipped | participating
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="matched",
        ),
        # Timestamps for notification and decision events
        sa.Column("notified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # Standard audit timestamps
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
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # T-07-schema-01: UNIQUE(user_id, tender_id) prevents duplicate match records
    # even under concurrent ARQ runs (Pitfall 3 in RESEARCH.md)
    op.create_unique_constraint(
        "uq_tender_matches_user_tender",
        "tender_matches",
        ["user_id", "tender_id"],
    )

    # Fast lookup by user (GET /api/discovery/matches)
    op.create_index("idx_tender_matches_user_id", "tender_matches", ["user_id"])

    # Used by run_matching worker to find unnotified matches
    op.create_index("idx_tender_matches_status", "tender_matches", ["status"])


def downgrade() -> None:
    op.drop_index("idx_tender_matches_status", table_name="tender_matches")
    op.drop_index("idx_tender_matches_user_id", table_name="tender_matches")
    op.drop_table("tender_matches")
