import datetime as dt

from sqlalchemy import DateTime, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JoinRequest(Base):
    """A user asking to join an organization with its join code; an org admin decides."""

    __tablename__ = "join_requests"
    __table_args__ = (
        Index("ix_join_requests_org_id_status", "org_id", "status"),
        Index("ix_join_requests_user_id", "user_id"),
        # At most one pending request per (org, user).
        Index(
            "uq_join_requests_pending",
            "org_id",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str] = mapped_column(String)
    org_name: Mapped[str] = mapped_column(String)
    user_id: Mapped[str] = mapped_column(String)
    user_name: Mapped[str] = mapped_column(String)
    user_email: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending", server_default="pending")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String)
