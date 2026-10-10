"""initial

Revision ID: 0001
Revises:
Create Date: 2026-10-10 13:51:18.751324
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "meetings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("project", sa.String(), nullable=True),
        sa.Column("organizer", sa.String(), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(), server_default="draft", nullable=False),
        sa.Column("source_filename", sa.String(), nullable=False),
        sa.Column("source_bytes", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_meetings_org_id_meeting_date", "meetings", ["org_id", "meeting_date"], unique=False
    )
    op.create_table(
        "dialogue_acts",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("meeting_id", sa.String(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("utterance_id", sa.String(), nullable=False),
        sa.Column("act", sa.String(), nullable=False),
        sa.Column("option", sa.String(), nullable=True),
        sa.Column("topic_id", sa.String(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pk"),
    )
    op.create_index("ix_dialogue_acts_meeting_id", "dialogue_acts", ["meeting_id"], unique=False)
    op.create_table(
        "items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("meeting_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("review_state", sa.String(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_items_meeting_id"), "items", ["meeting_id"], unique=False)
    op.create_index(op.f("ix_items_org_id"), "items", ["org_id"], unique=False)
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("meeting_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="queued", nullable=False),
        sa.Column("step", sa.String(), nullable=True),
        sa.Column("progress", sa.Float(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_meeting_id"), "jobs", ["meeting_id"], unique=False)
    op.create_index(op.f("ix_jobs_org_id"), "jobs", ["org_id"], unique=False)
    op.create_table(
        "topics",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("meeting_id", sa.String(), nullable=False),
        sa.Column("topic_id", sa.String(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("history", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ambiguous_decides", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pk"),
    )
    op.create_index("ix_topics_meeting_id", "topics", ["meeting_id"], unique=False)
    op.create_table(
        "utterances",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("meeting_id", sa.String(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(), nullable=False),
        sa.Column("start", sa.Float(), nullable=False),
        sa.Column("end", sa.Float(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint("meeting_id", "id", name="uq_utterances_meeting_id_id"),
    )
    op.create_index(
        "ix_utterances_meeting_id_seq", "utterances", ["meeting_id", "seq"], unique=False
    )
    op.create_table(
        "item_events",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_name", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pk"),
    )
    op.create_index("ix_item_events_item_id", "item_events", ["item_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_item_events_item_id", table_name="item_events")
    op.drop_table("item_events")
    op.drop_index("ix_utterances_meeting_id_seq", table_name="utterances")
    op.drop_table("utterances")
    op.drop_index("ix_topics_meeting_id", table_name="topics")
    op.drop_table("topics")
    op.drop_index(op.f("ix_jobs_org_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_meeting_id"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_items_org_id"), table_name="items")
    op.drop_index(op.f("ix_items_meeting_id"), table_name="items")
    op.drop_table("items")
    op.drop_index("ix_dialogue_acts_meeting_id", table_name="dialogue_acts")
    op.drop_table("dialogue_acts")
    op.drop_index("ix_meetings_org_id_meeting_date", table_name="meetings")
    op.drop_table("meetings")
