"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-06

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector  # type: ignore
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- clients ---
    op.create_table(
        "clients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("first_name", sa.Text, nullable=False),
        sa.Column("last_name", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("social_links", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute(
        """
        ALTER TABLE clients ADD COLUMN search_doc tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('simple',
                coalesce(first_name, '')), 'A') ||
            setweight(to_tsvector('simple',
                coalesce(last_name,  '')), 'A') ||
            setweight(to_tsvector('simple',
                coalesce(regexp_replace(email,
                    '[@.]', ' ', 'g'), '')), 'A') ||
            setweight(to_tsvector('simple',
                coalesce(description, '')), 'C') ||
            setweight(to_tsvector('simple', coalesce(
                regexp_replace(
                regexp_replace(
                regexp_replace(
                    social_links::text,
                    '[\\[\\]"]', '', 'g'),
                    ',', ' ', 'g'),
                    '[:/.]', ' ', 'g'),
                '')
            ), 'D')
        ) STORED
        """
    )
    op.create_unique_constraint("clients_email_key", "clients", ["email"])
    op.create_index(
        "clients_search_doc_gin",
        "clients",
        [sa.text("search_doc")],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_clients_created_at_id",
        "clients",
        ["created_at", "id"],
    )

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("documents_client_id_idx", "documents", ["client_id"])
    op.create_index(
        "ix_documents_created_at_id",
        "documents",
        ["created_at", "id"],
    )

    # --- document_chunks ---
    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("enriched_content", sa.Text, nullable=True),
        sa.Column("search_text", sa.Text, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("document_chunks_document_id_idx", "document_chunks", ["document_id"])
    op.create_unique_constraint(
        "uq_document_chunks_document_id_chunk_index",
        "document_chunks",
        ["document_id", "chunk_index"],
    )
    op.execute(
        """
        CREATE INDEX document_chunks_embedding_hnsw
        ON document_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )
    op.execute(
        """
        ALTER TABLE document_chunks ADD COLUMN search_doc tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(search_text, ''))) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX document_chunks_search_doc_gin
        ON document_chunks USING gin (search_doc)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS document_chunks_search_doc_gin")
    op.execute("DROP INDEX IF EXISTS document_chunks_embedding_hnsw")
    op.drop_constraint(
        "uq_document_chunks_document_id_chunk_index",
        "document_chunks",
        type_="unique",
    )
    op.drop_index("document_chunks_document_id_idx", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_documents_created_at_id", table_name="documents")
    op.drop_index("documents_client_id_idx", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_clients_created_at_id", table_name="clients")
    op.drop_index("clients_search_doc_gin", table_name="clients")
    op.drop_table("clients")
