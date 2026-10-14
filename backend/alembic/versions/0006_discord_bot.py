"""discord bot: linked Discord server and link code per org

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-14 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("org_settings", sa.Column("discord_guild_id", sa.String(), nullable=True))
    op.add_column("org_settings", sa.Column("discord_link_code", sa.String(), nullable=True))
    op.create_unique_constraint(
        "org_settings_discord_guild_id_key", "org_settings", ["discord_guild_id"]
    )
    op.create_unique_constraint(
        "org_settings_discord_link_code_key", "org_settings", ["discord_link_code"]
    )


def downgrade() -> None:
    op.drop_constraint("org_settings_discord_link_code_key", "org_settings", type_="unique")
    op.drop_constraint("org_settings_discord_guild_id_key", "org_settings", type_="unique")
    op.drop_column("org_settings", "discord_link_code")
    op.drop_column("org_settings", "discord_guild_id")
