"""Shared pipeline test data: payment_v2 transcript, context and fixture-backed FakeLLM."""

import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.config import AISettings
from app.ai.domain.models import MeetingContext, Participant
from app.ai.llm.fake import FakeLLM
from app.repositories import jobs, meetings
from app.services.analysis import run_analysis

FIX = Path(__file__).resolve().parents[1] / "fixtures"
PAYMENT = (FIX / "transcripts" / "payment_v2.txt").read_bytes()
CTX_PAYMENT = MeetingContext(
    meeting_id="m1",
    title="Payment sprint planning",
    meeting_date=date(2026, 10, 8),
    participants=[
        Participant(name="Lan", is_decision_maker=True),
        Participant(name="Minh"),
        Participant(name="Hoa"),
    ],
)


def fx(name: str) -> dict[str, Any]:
    return json.loads((FIX / "llm" / "payment_v2" / name).read_text(encoding="utf-8"))


def fake_from_fixtures() -> FakeLLM:
    return FakeLLM({"extract": [fx("extract.json")], "topics": [fx("topics.json")]})


async def seed_meeting(
    sm: async_sessionmaker[AsyncSession], *, org_id: str = "org_a", meeting_id: str = "m1"
) -> str:
    """Create an `analyzing` payment_v2 meeting with a queued analyze job; return the job id."""
    async with sm() as session:
        await meetings.create(
            session,
            org_id=org_id,
            created_by="user_1",
            ctx=CTX_PAYMENT.model_copy(update={"meeting_id": meeting_id}),
            filename="payment_v2.txt",
            data=PAYMENT,
        )
        await meetings.set_status(session, org_id=org_id, meeting_id=meeting_id, status="analyzing")
        job = await jobs.create(session, org_id=org_id, meeting_id=meeting_id, kind="analyze")
        await session.commit()
        return job.id


async def seed_analyzed_meeting(
    sm: async_sessionmaker[AsyncSession], org_id: str = "org_a", meeting_id: str = "m1"
) -> str:
    """Create an `in_review` payment_v2 meeting by running the analysis; return the meeting id."""
    job_id = await seed_meeting(sm, org_id=org_id, meeting_id=meeting_id)
    await run_analysis(
        sm, fake_from_fixtures(), AISettings(), org_id=org_id, meeting_id=meeting_id, job_id=job_id
    )
    return meeting_id


async def seed_published_indexed_meeting(
    sm: async_sessionmaker[AsyncSession],
    embedder: Any,
    org_id: str = "org_a",
    meeting_id: str = "m1",
    project: str | None = None,
) -> str:
    """Seed payment_v2, approve all items, publish, run the index job; return the meeting id."""
    from sqlalchemy import update

    from app.models import Item, Meeting
    from app.services.indexing import run_index

    await seed_analyzed_meeting(sm, org_id, meeting_id)
    async with sm() as s:
        await s.execute(
            update(Item).where(Item.meeting_id == meeting_id).values(review_state="approved")
        )
        if project is not None:
            await s.execute(update(Meeting).where(Meeting.id == meeting_id).values(project=project))
        await meetings.set_status(s, org_id=org_id, meeting_id=meeting_id, status="published")
        job = await jobs.create(s, org_id=org_id, meeting_id=meeting_id, kind="index")
        await s.commit()
        job_id = job.id
    await run_index(sm, embedder, org_id=org_id, meeting_id=meeting_id, job_id=job_id)
    return meeting_id
