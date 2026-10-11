"""retrieval: vector columns, transcript chunks, hnsw and trigram indexes

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("items", sa.Column("search_text", sa.Text(), nullable=True))
    op.add_column("items", sa.Column("embedding", Vector(1024), nullable=True))
    op.add_column("items", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "transcript_chunks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("meeting_id", sa.String(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("start_ts", sa.Float(), nullable=False),
        sa.Column("end_ts", sa.Float(), nullable=True),
        sa.Column("first_utterance_id", sa.String(), nullable=False),
        sa.Column("speakers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transcript_chunks_org_id", "transcript_chunks", ["org_id"])
    op.create_index("ix_transcript_chunks_meeting_id", "transcript_chunks", ["meeting_id"])
    op.create_index(
        "ix_items_embedding_hnsw",
        "items",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_items_search_text_trgm",
        "items",
        ["search_text"],
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_transcript_chunks_embedding_hnsw",
        "transcript_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_transcript_chunks_text_trgm",
        "transcript_chunks",
        ["text"],
        postgresql_using="gin",
        postgresql_ops={"text": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_transcript_chunks_text_trgm", table_name="transcript_chunks")
    op.drop_index("ix_transcript_chunks_embedding_hnsw", table_name="transcript_chunks")
    op.drop_index("ix_items_search_text_trgm", table_name="items")
    op.drop_index("ix_items_embedding_hnsw", table_name="items")
    op.drop_table("transcript_chunks")
    op.drop_column("items", "indexed_at")
    op.drop_column("items", "embedding")
    op.drop_column("items", "search_text")
