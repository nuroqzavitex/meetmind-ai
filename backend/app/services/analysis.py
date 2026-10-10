"""Run the analysis pipeline for a meeting and persist the outcome."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.config import AISettings
from app.ai.domain.models import MeetingContext
from app.ai.errors import AnalysisError, TranscriptParseError
from app.ai.llm.client import LLMClient
from app.ai.pipeline import analyze_transcript
from app.core.auth import Principal
from app.repositories import items, jobs, meetings

log = logging.getLogger(__name__)


async def _fail(
    sm: async_sessionmaker[AsyncSession],
    *,
    org_id: str,
    meeting_id: str,
    job_id: str,
    error: str,
    step: str | None = None,
) -> None:
    fields: dict[str, object] = {"status": "failed", "error": error}
    if step is not None:
        fields["step"] = step
    async with sm() as session:
        await jobs.update(session, org_id=org_id, job_id=job_id, **fields)
        await meetings.set_status(session, org_id=org_id, meeting_id=meeting_id, status="failed")
        await session.commit()


async def _safe_fail(
    sm: async_sessionmaker[AsyncSession],
    *,
    org_id: str,
    meeting_id: str,
    job_id: str,
    error: str,
    step: str | None = None,
) -> None:
    """Mark the run failed; a failure here is logged and never masks the original error."""
    try:
        await _fail(
            sm, org_id=org_id, meeting_id=meeting_id, job_id=job_id, error=error, step=step
        )
    except Exception:
        log.exception("could not mark job %s / meeting %s as failed", job_id, meeting_id)


async def run_analysis(
    sm: async_sessionmaker[AsyncSession],
    llm: LLMClient,
    ai: AISettings,
    *,
    org_id: str,
    meeting_id: str,
    job_id: str,
) -> None:
    async with sm() as session:
        meeting = await meetings.get(
            session, org_id=org_id, meeting_id=meeting_id, with_source=True
        )
        job = await jobs.get(session, org_id=org_id, job_id=job_id)
        if meeting is None or job is None:
            log.warning("analysis skipped: meeting %s or job %s not found", meeting_id, job_id)
            return
        if job.status != "queued":
            log.warning("analysis skipped: job %s is %s, not queued", job_id, job.status)
            return
        raw_ctx = meeting.context
        filename, data = meeting.source_filename, meeting.source_bytes
        await jobs.update(
            session, org_id=org_id, job_id=job_id, status="running", step="start", progress=0.0
        )
        await session.commit()

    async def on_progress(step: str, value: float) -> None:
        async with sm() as s:
            await jobs.update(s, org_id=org_id, job_id=job_id, step=step, progress=value)
            await s.commit()

    try:
        ctx = MeetingContext(**raw_ctx)
        result = await analyze_transcript(
            ctx=ctx, filename=filename, data=data, llm=llm, settings=ai, on_progress=on_progress
        )
        actor = Principal(user_id="system", org_id=org_id, name="MeetMind AI")
        async with sm() as session:
            await meetings.replace_analysis(
                session,
                org_id=org_id,
                meeting_id=meeting_id,
                utterances=result.utterances,
                acts=result.acts,
                topics=result.topics,
            )
            rows = await items.replace_for_meeting(
                session, org_id=org_id, meeting_id=meeting_id, items=result.items
            )
            for row in rows:
                await items.add_event(
                    session, item=row, actor=actor, action="created", before=None, after=row.data
                )
            await meetings.set_status(
                session, org_id=org_id, meeting_id=meeting_id, status="in_review"
            )
            await jobs.update(
                session,
                org_id=org_id,
                job_id=job_id,
                status="succeeded",
                progress=1.0,
                result={"items": len(rows)},
            )
            await session.commit()
    except AnalysisError as e:
        await _safe_fail(
            sm, org_id=org_id, meeting_id=meeting_id, job_id=job_id,
            error=f"Bước {e.step} lỗi: {e}", step=e.step,
        )
    except TranscriptParseError as e:
        await _safe_fail(
            sm, org_id=org_id, meeting_id=meeting_id, job_id=job_id,
            error=f"Không đọc được transcript: {e}",
        )
    except asyncio.CancelledError:
        # arq job_timeout / abort: record the interruption, then let the cancellation propagate.
        log.warning("analysis of meeting %s was cancelled", meeting_id)
        await _safe_fail(
            sm, org_id=org_id, meeting_id=meeting_id, job_id=job_id,
            error="Phân tích bị gián đoạn hoặc quá thời gian",
        )
        raise
    except Exception:
        log.exception("unexpected error analysing meeting %s", meeting_id)
        await _safe_fail(
            sm, org_id=org_id, meeting_id=meeting_id, job_id=job_id,
            error="Lỗi không mong muốn khi phân tích",
        )
