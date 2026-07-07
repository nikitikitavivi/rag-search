"""add metadata jsonb to document_chunks

Revision ID: 0002_chunk_metadata
Revises: 0001_initial
Create Date: 2026-07-07

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002_chunk_metadata"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("metadata", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "metadata")
