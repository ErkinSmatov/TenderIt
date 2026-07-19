"""extend_tenders_source_fields

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-19

Adds three columns to the tenders table for Phase 7 Discovery & Matching:
  - source TEXT NOT NULL DEFAULT 'goszakup' — future multi-source support (D-01: only goszakup for now)
  - region TEXT nullable — region matching in client_filters
  - spgz_code TEXT nullable — СПГЗ code for exact-match filter (field name TBD: see 07-02 Task 1)

Per D-01 (07-CONTEXT.md): NO UNIQUE(source, external_number) constraint added.
Existing UNIQUE(number_anno) on tenders is sufficient — sk.kz is deferred to v2.

Per RESEARCH pitfall 4: end_date IS the submission deadline. DO NOT add deadline_at.
Per RESEARCH section: raw_data already exists. DO NOT rename to raw_payload.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source column — NOT NULL with server default so existing rows are backfilled
    op.add_column(
        "tenders",
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            server_default="goszakup",
        ),
    )
    # Add region column — nullable, populated by poll worker from goszakup batch response
    op.add_column(
        "tenders",
        sa.Column("region", sa.Text(), nullable=True),
    )
    # Add spgz_code column — nullable; field name in goszakup GraphQL Lots confirmed at 07-02
    # (see 07-RESEARCH.md Pitfall 7 and Open Questions section)
    op.add_column(
        "tenders",
        sa.Column("spgz_code", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenders", "spgz_code")
    op.drop_column("tenders", "region")
    op.drop_column("tenders", "source")
