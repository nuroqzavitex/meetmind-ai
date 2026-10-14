"""org settings: per-org Discord webhook and daily digest toggle

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "org_settings",
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("discord_webhook_url", sa.String(), nullable=True),
        sa.Column("digest_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("org_id"),
    )


def downgrade() -> None:
    op.drop_table("org_settings")
