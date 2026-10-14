import datetime as dt

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrgSettings(Base):
    """Per-organisation settings; one row per org, created on first save."""

    __tablename__ = "org_settings"

    org_id: Mapped[str] = mapped_column(String, primary_key=True)
    discord_webhook_url: Mapped[str | None] = mapped_column(String)
    digest_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
