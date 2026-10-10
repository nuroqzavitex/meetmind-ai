import datetime as dt
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Meeting(Base):
    __tablename__ = "meetings"
    __table_args__ = (Index("ix_meetings_org_id_meeting_date", "org_id", "meeting_date"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str] = mapped_column(String)
    created_by: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    meeting_date: Mapped[dt.date]
    project: Mapped[str | None] = mapped_column(String)
    organizer: Mapped[str | None] = mapped_column(String)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String, default="draft", server_default="draft")
    source_filename: Mapped[str] = mapped_column(String)
    source_bytes: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Utterance(Base):
    __tablename__ = "utterances"
    __table_args__ = (
        UniqueConstraint("meeting_id", "id", name="uq_utterances_meeting_id_id"),
        Index("ix_utterances_meeting_id_seq", "meeting_id", "seq"),
    )

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"))
    id: Mapped[str] = mapped_column(String)
    seq: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float | None] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
