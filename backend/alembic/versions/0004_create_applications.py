"""create_applications

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-09

Creates:
  - applications: tender application state machine table
    Columns: id, user_id (FK→users ON DELETE CASCADE), tender_id (FK→tenders ON DELETE CASCADE),
             lots_data (JSONB NOT NULL), document_ids (INTEGER[] NOT NULL DEFAULT '{}'),
             goszakup_application_id (BIGINT nullable), goszakup_tender_buy_id (BIGINT nullable),
             status (TEXT NOT NULL DEFAULT 'draft'), error_message (TEXT nullable),
             retry_count (INTEGER NOT NULL DEFAULT 0), created_at (TIMESTAMPTZ NOT NULL DEFAULT now()),
             ready_at (TIMESTAMPTZ nullable), submitted_at (TIMESTAMPTZ nullable),
             updated_at (TIMESTAMPTZ NOT NULL DEFAULT now())
  - Indexes:
    idx_applications_user_id  — for GET /api/applications (list by user)
    idx_applications_status   — partial index on ('waiting', 'submitting') for ARQ polling

Alters:
  - users: adds telegram_chat_id BIGINT nullable (D-05-06: Telegram notify flow)

Per D-05-04 (05-CONTEXT.md, Machine State section):
  status values: draft | signed | waiting | submitting | submitted | error
  Stored as TEXT (not PG ENUM) for easy v2 extension.

Threat mitigations:
  T-05-06: Redis TTL 72000s on goszakup_session — session data is NOT stored in PostgreSQL.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add telegram_chat_id to users (D-05-06 — Telegram notification flow)
    op.add_column(
        "users",
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
    )

    # Create applications table (D-05-04 — state machine schema)
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tender_id", sa.Integer(), nullable=False),
        # Draft data (lots, documents) — stored in TenderIt, not on goszakup portal
        sa.Column("lots_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "document_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default="{}",
        ),
        # goszakup portal IDs — filled after browser completes steps 1-11
        sa.Column("goszakup_application_id", sa.BigInteger(), nullable=True),
        sa.Column("goszakup_tender_buy_id", sa.BigInteger(), nullable=True),
        # State machine — TEXT not PG ENUM (D-05-04 decision: easy v2 extension)
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ready_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=True),
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

    # Fast lookup by user (GET /api/applications)
    op.create_index("idx_applications_user_id", "applications", ["user_id"])

    # Partial index for ARQ polling — only rows the worker actually queries
    op.create_index(
        "idx_applications_status",
        "applications",
        ["status"],
        postgresql_where=sa.text("status IN ('waiting', 'submitting')"),
    )


def downgrade() -> None:
    op.drop_index("idx_applications_status", table_name="applications")
    op.drop_index("idx_applications_user_id", table_name="applications")
    op.drop_table("applications")
    op.drop_column("users", "telegram_chat_id")
