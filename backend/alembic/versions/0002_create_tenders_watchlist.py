"""create_tenders_watchlist

Revision ID: 0002
Revises: 861194df635a
Create Date: 2026-06-10

Creates:
  - tenders: goszakup tender cache with JSONB lots_data / raw_data and TIMESTAMPTZ columns
  - user_watchlist: user → tender M2M with ON DELETE CASCADE and unique(user_id, tender_id)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "861194df635a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number_anno", sa.String(length=100), nullable=False),
        sa.Column("name_ru", sa.Text(), nullable=True),
        sa.Column("name_kz", sa.Text(), nullable=True),
        sa.Column("total_sum", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("customer_name_ru", sa.String(length=500), nullable=True),
        sa.Column("customer_name_kz", sa.String(length=500), nullable=True),
        sa.Column("status_id", sa.Integer(), nullable=True),
        sa.Column("status_name_ru", sa.String(length=200), nullable=True),
        sa.Column("start_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("end_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("publish_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("lots_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "cached_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number_anno"),
    )
    op.create_index(
        "ix_tenders_number_anno", "tenders", ["number_anno"], unique=True
    )

    op.create_table(
        "user_watchlist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tender_id", sa.Integer(), nullable=False),
        sa.Column(
            "added_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "notification_on",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tender_id"], ["tenders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tender_id", name="uq_user_watchlist"),
    )


def downgrade() -> None:
    op.drop_table("user_watchlist")
    op.drop_index("ix_tenders_number_anno", table_name="tenders")
    op.drop_table("tenders")
