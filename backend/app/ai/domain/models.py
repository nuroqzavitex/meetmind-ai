"""Pydantic domain models for the AI core (spec section 7.1)."""

from datetime import date

from pydantic import BaseModel, Field

from app.ai.domain.enums import Act, ItemStatus, ItemType, ReviewState


class Participant(BaseModel):
    name: str
    role: str | None = None
    is_decision_maker: bool = False


class MeetingContext(BaseModel):
    meeting_id: str
    title: str
    meeting_date: date
    project: str | None = None
    organizer: str | None = None
    participants: list[Participant] = []
    glossary: list[str] = []


class Utterance(BaseModel):
    id: str                               # "u0042"
    seq: int                              # thứ tự trong transcript, bắt đầu từ 0
    speaker: str
    start: float                          # giây
    end: float | None = None
    text: str


class DialogueAct(BaseModel):
    id: str
    utterance_id: str                     # LLM phải trả về đúng id câu được gán
    seq: int                              # sao từ Utterance.seq (code điền, không do LLM)
    speaker: str
    start: float
    act: Act
    quote: str                            # NGUYÊN VĂN, là đoạn con của câu utterance_id
    topic_hint: str | None = None
    topic_id: str | None = None           # do bước topics gán
    option: str | None = None
    content: str | None = None
    assignee: str | None = None
    due_text: str | None = None           # LLM chỉ trích chữ; due_date do code tính
    due_date: date | None = None
    condition: str | None = None
    confidence: float = Field(ge=0, le=1, default=0.7)


class Evidence(BaseModel):
    utterance_id: str
    speaker: str
    ts: str                               # "00:47:12"
    quote: str


class MeetingItem(BaseModel):
    id: str
    meeting_id: str
    type: ItemType
    topic_id: str | None = None
    content: str
    status: ItemStatus = ItemStatus.FINAL
    supersedes: list[str] = []
    superseded_by: str | None = None
    rationale: str | None = None
    owner: str | None = None
    requester: str | None = None
    due_date: date | None = None
    due_text: str | None = None
    condition: str | None = None
    confidence: float = 0.7
    flags: list[str] = []
    evidence: list[Evidence]
    review_state: ReviewState = ReviewState.PENDING
