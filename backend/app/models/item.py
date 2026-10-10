import datetime as dt
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DialogueActRow(Base):
    __tablename__ = "dialogue_acts"
    __table_args__ = (Index("ix_dialogue_acts_meeting_id", "meeting_id"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"))
    id: Mapped[str] = mapped_column(String)
    utterance_id: Mapped[str] = mapped_column(String)
    act: Mapped[str] = mapped_column(String)
    option: Mapped[str | None] = mapped_column(String)
    topic_id: Mapped[str | None] = mapped_column(String)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)


class TopicRow(Base):
    __tablename__ = "topics"
    __table_args__ = (Index("ix_topics_meeting_id", "meeting_id"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"))
    topic_id: Mapped[str] = mapped_column(String)
    question: Mapped[str] = mapped_column(Text)
    history: Mapped[dict[str, Any]] = mapped_column(JSONB)
    ambiguous_decides: Mapped[list[Any]] = mapped_column(JSONB)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str] = mapped_column(String, index=True)
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    review_state: Mapped[str] = mapped_column(String)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    position: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ItemEvent(Base):
    __tablename__ = "item_events"
    __table_args__ = (Index("ix_item_events_item_id", "item_id"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    actor_id: Mapped[str] = mapped_column(String)
    actor_name: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
