"""join requests: org join code and requests to join an organization

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-14 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("org_settings", sa.Column("join_code", sa.String(), nullable=True))
    op.create_unique_constraint("org_settings_join_code_key", "org_settings", ["join_code"])
    op.create_table(
        "join_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("org_name", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("user_name", sa.String(), nullable=False),
        sa.Column("user_email", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_join_requests_org_id_status", "join_requests", ["org_id", "status"])
    op.create_index("ix_join_requests_user_id", "join_requests", ["user_id"])
    op.create_index(
        "uq_join_requests_pending",
        "join_requests",
        ["org_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_join_requests_pending", table_name="join_requests")
    op.drop_index("ix_join_requests_user_id", table_name="join_requests")
    op.drop_index("ix_join_requests_org_id_status", table_name="join_requests")
    op.drop_table("join_requests")
    op.drop_constraint("org_settings_join_code_key", "org_settings", type_="unique")
    op.drop_column("org_settings", "join_code")
