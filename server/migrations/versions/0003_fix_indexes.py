"""Fix indexes: drop duplicate email index, add (document_id, chunk_index)
unique constraint, add keyset pagination composite indexes.

Revision ID: 0003_fix_indexes
Revises: 0002_chunk_metadata
Create Date: 2026-07-07
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0003_fix_indexes"
down_revision: str | None = "0002_chunk_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("clients_email_idx", table_name="clients")

    op.create_unique_constraint(
        "uq_document_chunks_document_id_chunk_index",
        "document_chunks",
        ["document_id", "chunk_index"],
    )

    op.create_index(
        "ix_clients_created_at_id",
        "clients",
        ["created_at", "id"],
    )
    op.create_index(
        "ix_documents_created_at_id",
        "documents",
        ["created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_created_at_id", table_name="documents")
    op.drop_index("ix_clients_created_at_id", table_name="clients")

    op.drop_constraint(
        "uq_document_chunks_document_id_chunk_index",
        "document_chunks",
        type_="unique",
    )

    op.create_index("clients_email_idx", "clients", ["email"], unique=True)
