"""create_documents

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-11

Creates:
  - documents: user document metadata with MinIO file_key reference
    Columns: id, user_id (FK→users ON DELETE CASCADE), file_name, file_key,
             file_size, mime_type, category (TEXT), expires_at (TIMESTAMPTZ nullable),
             uploaded_at (TIMESTAMPTZ NOT NULL DEFAULT now())
  - Indexes:
    ix_documents_user_id       — for GET /api/documents (list by user)
    ix_documents_user_expires  — for GET /api/documents/attachable (filter by expiry)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_key", sa.String(1000), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])
    op.create_index(
        "ix_documents_user_expires", "documents", ["user_id", "expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_documents_user_expires", table_name="documents")
    op.drop_index("ix_documents_user_id", table_name="documents")
    op.drop_table("documents")
