"""Meeting and job use-cases."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.domain.models import MeetingContext
from app.ai.errors import TranscriptParseError
from app.ai.parsing import parse_transcript
from app.core.auth import Principal
from app.core.config import STALE_JOB_SECONDS
from app.core.errors import Conflict, NotFound, PayloadTooLarge, ServiceUnavailable, Unprocessable
from app.repositories import jobs, meetings
from app.schemas.jobs import JobOut
from app.schemas.meetings import (
    MeetingContextIn,
    MeetingCreated,
    MeetingDetail,
    MeetingSummary,
)
from app.workers.queue import JobQueue

logger = logging.getLogger(__name__)


async def _enqueue(
    session: AsyncSession, queue: JobQueue, *, org_id: str, meeting_id: str, job_id: str
) -> None:
    """Enqueue after commit; on failure mark job and meeting failed and raise 503."""
    try:
        await queue.enqueue("analyze", org_id=org_id, meeting_id=meeting_id, job_id=job_id)
    except Exception:
        logger.exception("Failed to enqueue job %s", job_id)
        message = "Không đưa được job vào hàng đợi"
        try:
            await jobs.update(session, org_id=org_id, job_id=job_id, status="failed", error=message)
            await meetings.set_status(
                session, org_id=org_id, meeting_id=meeting_id, status="failed"
            )
            await session.commit()
        except Exception:
            logger.exception("Failed to mark job %s as failed after enqueue error", job_id)
        raise ServiceUnavailable(message, "queue_unavailable") from None


async def create_meeting(
    session: AsyncSession,
    queue: JobQueue,
    *,
    principal: Principal,
    ctx_in: MeetingContextIn,
    filename: str,
    data: bytes,
    max_bytes: int,
) -> MeetingCreated:
    if len(data) > max_bytes:
        raise PayloadTooLarge("Tệp vượt quá dung lượng cho phép")
    if not data:
        raise Unprocessable("Tệp rỗng", "transcript_parse_error")
    try:
        utterances = parse_transcript(filename, data)
    except TranscriptParseError as exc:
        raise Unprocessable(str(exc), "transcript_parse_error") from exc
    if not utterances:
        raise Unprocessable("Không tìm thấy câu thoại nào", "transcript_parse_error")

    meeting_id = str(uuid.uuid4())
    ctx = MeetingContext(meeting_id=meeting_id, **ctx_in.model_dump())
    org_id = principal.org_id
    await meetings.create(
        session, org_id=org_id, created_by=principal.user_id, ctx=ctx, filename=filename, data=data
    )
    await meetings.set_status(session, org_id=org_id, meeting_id=meeting_id, status="analyzing")
    job = await jobs.create(session, org_id=org_id, meeting_id=meeting_id, kind="analyze")
    await session.commit()
    await _enqueue(session, queue, org_id=org_id, meeting_id=meeting_id, job_id=job.id)
    return MeetingCreated(meeting_id=meeting_id, job_id=job.id)


async def list_meetings(
    session: AsyncSession,
    *,
    principal: Principal,
    project: str | None = None,
    status: str | None = None,
) -> list[MeetingSummary]:
    rows = await meetings.list_(session, org_id=principal.org_id, project=project, status=status)
    return [MeetingSummary.model_validate(r) for r in rows]


async def get_meeting(
    session: AsyncSession, *, principal: Principal, meeting_id: str
) -> MeetingDetail:
    org_id = principal.org_id
    row = await meetings.get(session, org_id=org_id, meeting_id=meeting_id)
    if row is None:
        raise NotFound("Không tìm thấy cuộc họp")
    utterances = await meetings.get_utterances(session, org_id=org_id, meeting_id=meeting_id)
    active = await jobs.active_for_meeting(session, org_id=org_id, meeting_id=meeting_id)
    latest = await jobs.latest_for_meeting(session, org_id=org_id, meeting_id=meeting_id)
    summary = MeetingSummary.model_validate(row)
    return MeetingDetail(
        **summary.model_dump(),
        context=MeetingContext.model_validate(row.context),
        utterances=utterances,
        active_job_id=active.id if active else None,
        latest_job=JobOut.model_validate(latest) if latest else None,
    )


async def get_job(session: AsyncSession, *, principal: Principal, job_id: str) -> JobOut:
    row = await jobs.get(session, org_id=principal.org_id, job_id=job_id)
    if row is None:
        raise NotFound("Không tìm thấy job")
    return JobOut.model_validate(row)


async def reanalyze(
    session: AsyncSession, queue: JobQueue, *, principal: Principal, meeting_id: str
) -> MeetingCreated:
    org_id = principal.org_id
    row = await meetings.get(session, org_id=org_id, meeting_id=meeting_id)
    if row is None:
        raise NotFound("Không tìm thấy cuộc họp")
    moved = await meetings.transition_status(
        session,
        org_id=org_id,
        meeting_id=meeting_id,
        from_status="failed",
        to_status="analyzing",
    )
    if not moved and row.status == "analyzing":
        # A job that outlived the worker timeout is dead: fail it and allow a retry.
        moved = bool(
            await jobs.fail_stale(
                session,
                org_id=org_id,
                meeting_id=meeting_id,
                older_than_seconds=STALE_JOB_SECONDS,
                error="Phân tích bị gián đoạn hoặc quá thời gian",
            )
        )
    if not moved:
        raise Conflict("Chỉ có thể phân tích lại cuộc họp bị lỗi", "not_failed")
    job = await jobs.create(session, org_id=org_id, meeting_id=meeting_id, kind="analyze")
    await session.commit()
    await _enqueue(session, queue, org_id=org_id, meeting_id=meeting_id, job_id=job.id)
    return MeetingCreated(meeting_id=meeting_id, job_id=job.id)
