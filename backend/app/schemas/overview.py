from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.ai.domain.enums import ItemStatus, ItemType
from app.ai.domain.models import Hold

DueState = Literal["overdue", "today", "soon", "later"]


class OverviewEntry(BaseModel):
    """One published item, with the meeting it comes from and its first piece of evidence."""

    item_id: str
    meeting_id: str
    meeting_title: str
    meeting_date: date
    project: str | None
    type: ItemType
    status: ItemStatus
    content: str
    owner: str | None = None
    due_date: date | None = None
    due_state: DueState | None = None
    condition: str | None = None
    supersedes: list[str] = []
    hold: Hold | None = None
    speaker: str | None = None
    ts: str | None = None
    quote: str | None = None
    utterance_id: str | None = None


class AgendaOut(BaseModel):
    """Next-meeting agenda built from what published meetings left open (no LLM)."""

    project: str | None
    projects: list[str]
    generated_on: date
    to_decide: list[OverviewEntry]
    conditions: list[OverviewEntry]
    due: list[OverviewEntry]
    markdown: str


class TasksOut(BaseModel):
    projects: list[str]
    owners: list[str]
    tasks: list[OverviewEntry]


class DecisionsOut(BaseModel):
    projects: list[str]
    decisions: list[OverviewEntry]


class AgendaSentOut(BaseModel):
    sent: bool
