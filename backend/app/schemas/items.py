from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.domain.enums import ItemStatus
from app.ai.domain.models import MeetingItem
from app.ai.domain.state_machine import Topic


class ItemOut(MeetingItem):
    """Mirrors the domain `MeetingItem`."""


class TopicOut(Topic):
    """Mirrors the domain `Topic`."""


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str | None = None
    status: ItemStatus | None = None
    owner: str | None = None
    requester: str | None = None
    due_date: date | None = None
    rationale: str | None = None
    condition: str | None = None

    @field_validator("content")
    @classmethod
    def _content_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("content must not be blank")
        return v

    @field_validator("owner", "requester")
    @classmethod
    def _strip_blank_to_none(cls, v: str | None) -> str | None:
        return (v.strip() or None) if v is not None else None


class ItemAction(BaseModel):
    action: Literal["approve", "edit", "reject"]
    patch: ItemPatch | None = None
    reason: str | None = Field(default=None, max_length=1000)


class ApproveCleanOut(BaseModel):
    approved: int


class ItemEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action: str
    actor_name: str
    reason: str | None
    created_at: datetime
