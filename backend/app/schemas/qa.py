from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


class QARequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    project: str | None = Field(default=None, max_length=200)


class Citation(BaseModel):
    ref: int
    meeting_id: str
    title: str
    date: date
    ts: str
    speaker: str
    quote: str
    utterance_id: str


class QAResponse(BaseModel):
    answer: str
    citations: list[Citation]
