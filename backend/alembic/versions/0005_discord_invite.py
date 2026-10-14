"""discord invite: public invite link to the team's Discord server

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-14 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("org_settings", sa.Column("discord_invite_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("org_settings", "discord_invite_url")
