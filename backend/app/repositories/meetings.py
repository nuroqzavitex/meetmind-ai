from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.ai.domain.models import DialogueAct, MeetingContext, Utterance
from app.ai.domain.state_machine import Topic
from app.models import DialogueActRow, Meeting, TopicRow
from app.models import Utterance as UtteranceRow


async def create(
    session: AsyncSession,
    *,
    org_id: str,
    created_by: str,
    ctx: MeetingContext,
    filename: str,
    data: bytes,
) -> Meeting:
    meeting = Meeting(
        id=ctx.meeting_id,
        org_id=org_id,
        created_by=created_by,
        title=ctx.title,
        meeting_date=ctx.meeting_date,
        project=ctx.project,
        organizer=ctx.organizer,
        context=ctx.model_dump(mode="json"),
        status="draft",
        source_filename=filename,
        source_bytes=data,
    )
    session.add(meeting)
    await session.flush()
    return meeting


async def get(
    session: AsyncSession, *, org_id: str, meeting_id: str, with_source: bool = False
) -> Meeting | None:
    stmt = select(Meeting).where(Meeting.id == meeting_id, Meeting.org_id == org_id)
    if with_source:
        stmt = stmt.options(undefer(Meeting.source_bytes))
    return await session.scalar(stmt)


async def list_(
    session: AsyncSession,
    *,
    org_id: str,
    project: str | None = None,
    status: str | None = None,
) -> list[Meeting]:
    stmt = select(Meeting).where(Meeting.org_id == org_id)
    if project is not None:
        stmt = stmt.where(Meeting.project == project)
    if status is not None:
        stmt = stmt.where(Meeting.status == status)
    stmt = stmt.order_by(Meeting.meeting_date.desc(), Meeting.created_at.desc())
    return list((await session.scalars(stmt)).all())


async def set_status(
    session: AsyncSession,
    *,
    org_id: str,
    meeting_id: str,
    status: str,
    published_at: datetime | None = None,
) -> None:
    values: dict[str, object] = {"status": status}
    if published_at is not None:
        values["published_at"] = published_at
    await session.execute(
        update(Meeting).where(Meeting.id == meeting_id, Meeting.org_id == org_id).values(**values)
    )


async def transition_status(
    session: AsyncSession,
    *,
    org_id: str,
    meeting_id: str,
    from_status: str,
    to_status: str,
) -> bool:
    """Atomically move a meeting between statuses; False if it was not in `from_status`."""
    result = await session.execute(
        update(Meeting)
        .where(Meeting.id == meeting_id, Meeting.org_id == org_id, Meeting.status == from_status)
        .values(status=to_status)
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]


async def replace_source(
    session: AsyncSession, *, org_id: str, meeting_id: str, filename: str, data: bytes
) -> None:
    await session.execute(
        update(Meeting)
        .where(Meeting.id == meeting_id, Meeting.org_id == org_id)
        .values(source_filename=filename, source_bytes=data)
    )


async def update_context(
    session: AsyncSession, *, org_id: str, meeting_id: str, ctx: MeetingContext
) -> None:
    await session.execute(
        update(Meeting)
        .where(Meeting.id == meeting_id, Meeting.org_id == org_id)
        .values(context=ctx.model_dump(mode="json"))
    )


async def replace_analysis(
    session: AsyncSession,
    *,
    org_id: str,
    meeting_id: str,
    utterances: list[Utterance],
    acts: list[DialogueAct],
    topics: list[Topic],
) -> None:
    if await get(session, org_id=org_id, meeting_id=meeting_id) is None:
        return
    for model in (UtteranceRow, DialogueActRow, TopicRow):
        await session.execute(delete(model).where(model.meeting_id == meeting_id))
    session.add_all(
        UtteranceRow(
            meeting_id=meeting_id,
            id=u.id,
            seq=u.seq,
            speaker=u.speaker,
            start=u.start,
            end=u.end,
            text=u.text,
        )
        for u in utterances
    )
    session.add_all(
        DialogueActRow(
            meeting_id=meeting_id,
            id=a.id,
            utterance_id=a.utterance_id,
            act=a.act.value,
            option=a.option,
            topic_id=a.topic_id,
            payload=a.model_dump(mode="json"),
        )
        for a in acts
    )
    session.add_all(
        TopicRow(
            meeting_id=meeting_id,
            topic_id=t.topic_id,
            question=t.question,
            history=t.model_dump(mode="json"),
            ambiguous_decides=[a.model_dump(mode="json") for a in t.ambiguous_decides],
        )
        for t in topics
    )
    await session.flush()


async def get_utterances(session: AsyncSession, *, org_id: str, meeting_id: str) -> list[Utterance]:
    stmt = (
        select(UtteranceRow)
        .join(Meeting, Meeting.id == UtteranceRow.meeting_id)
        .where(Meeting.org_id == org_id, UtteranceRow.meeting_id == meeting_id)
        .order_by(UtteranceRow.seq)
    )
    rows = (await session.scalars(stmt)).all()
    return [
        Utterance(id=r.id, seq=r.seq, speaker=r.speaker, start=r.start, end=r.end, text=r.text)
        for r in rows
    ]


async def get_topics(session: AsyncSession, *, org_id: str, meeting_id: str) -> list[Topic]:
    stmt = (
        select(TopicRow)
        .join(Meeting, Meeting.id == TopicRow.meeting_id)
        .where(Meeting.org_id == org_id, TopicRow.meeting_id == meeting_id)
        .order_by(TopicRow.pk)
    )
    return [Topic.model_validate(r.history) for r in (await session.scalars(stmt)).all()]
