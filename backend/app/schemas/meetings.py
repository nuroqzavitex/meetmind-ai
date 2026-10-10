from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.ai.domain.models import MeetingContext, Participant, Utterance
from app.schemas.jobs import JobOut


class MeetingContextIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    meeting_date: date
    project: str | None = Field(default=None, max_length=200)
    organizer: str | None = Field(default=None, max_length=200)
    participants: list[Participant] = Field(default=[], max_length=100)
    glossary: list[str] = Field(default=[], max_length=500)


class MeetingCreated(BaseModel):
    meeting_id: str
    job_id: str


class MeetingSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    meeting_date: date
    project: str | None
    status: str
    created_at: datetime
    published_at: datetime | None


class MeetingDetail(MeetingSummary):
    context: MeetingContext
    utterances: list[Utterance]
    active_job_id: str | None
    latest_job: JobOut | None = None
