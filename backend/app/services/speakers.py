"""Speaker name assignment for transcribed audio, then hand-off to the normal analysis job."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.domain.models import MeetingContext, Participant
from app.ai.stt import rename_speakers, speaker_summary
from app.core.auth import Principal
from app.core.errors import Conflict, NotFound, Unprocessable
from app.models import Meeting
from app.repositories import jobs, meetings
from app.schemas.meetings import MeetingCreated
from app.schemas.speakers import SpeakerOut, SpeakersIn
from app.services.meetings import _enqueue
from app.workers.queue import JobQueue

_NOT_AWAITING = "Cuộc họp không ở bước gán người nói"


async def _awaiting_meeting(session: AsyncSession, principal: Principal, meeting_id: str) -> Meeting:
    row = await meetings.get(session, org_id=principal.org_id, meeting_id=meeting_id, with_source=True)
    if row is None:
        raise NotFound("Không tìm thấy cuộc họp")
    if row.status != "awaiting_speakers":
        raise Conflict(_NOT_AWAITING, "not_awaiting_speakers")
    return row


async def get_speakers(
    session: AsyncSession, *, principal: Principal, meeting_id: str
) -> list[SpeakerOut]:
    row = await _awaiting_meeting(session, principal, meeting_id)
    return [
        SpeakerOut(label=label, count=count, samples=samples)
        for label, count, samples in speaker_summary(row.source_bytes)
    ]


async def assign_speakers(
    session: AsyncSession,
    queue: JobQueue,
    *,
    principal: Principal,
    meeting_id: str,
    body: SpeakersIn,
) -> MeetingCreated:
    org_id = principal.org_id
    row = await _awaiting_meeting(session, principal, meeting_id)
    labels = [label for label, _, _ in speaker_summary(row.source_bytes)]
    given = [s.label for s in body.speakers]
    if sorted(given) != sorted(labels):
        raise Unprocessable("Cần gán tên cho đúng và đủ mọi người nói", "speakers_mismatch")
    names = [s.name.casefold() for s in body.speakers]
    if len(set(names)) != len(names):
        raise Unprocessable("Mỗi người nói phải có một tên khác nhau", "duplicate_speaker_name")

    # Atomic guard: a second submission (or a race) finds the meeting no longer awaiting.
    moved = await meetings.transition_status(
        session,
        org_id=org_id,
        meeting_id=meeting_id,
        from_status="awaiting_speakers",
        to_status="analyzing",
    )
    if not moved:
        raise Conflict(_NOT_AWAITING, "not_awaiting_speakers")
    mapping = {s.label: s.name for s in body.speakers}
    await meetings.replace_source(
        session,
        org_id=org_id,
        meeting_id=meeting_id,
        filename=row.source_filename,
        data=rename_speakers(row.source_bytes, mapping),
    )
    ctx = MeetingContext.model_validate(row.context).model_copy(
        update={
            "participants": [
                Participant(name=s.name, is_decision_maker=s.is_decision_maker)
                for s in body.speakers
            ]
        }
    )
    await meetings.update_context(session, org_id=org_id, meeting_id=meeting_id, ctx=ctx)
    job = await jobs.create(session, org_id=org_id, meeting_id=meeting_id, kind="analyze")
    await session.commit()
    await _enqueue(session, queue, org_id=org_id, meeting_id=meeting_id, job_id=job.id)
    return MeetingCreated(meeting_id=meeting_id, job_id=job.id)
