"""Transcribe an uploaded audio file into a speaker-labelled transcript awaiting name assignment."""

import asyncio
import logging
from pathlib import PurePath

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.errors import STTError
from app.ai.stt import SpeechToText, label_speakers, to_transcript_txt
from app.repositories import jobs, meetings
from app.services.analysis import safe_fail

log = logging.getLogger(__name__)

NO_SPEECH = "Không nhận được lời thoại nào từ file audio"


async def run_transcription(
    sm: async_sessionmaker[AsyncSession],
    stt: SpeechToText,
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
            log.warning("transcription skipped: meeting %s or job %s not found", meeting_id, job_id)
            return
        if job.status != "queued":
            log.warning("transcription skipped: job %s is %s, not queued", job_id, job.status)
            return
        filename, data = meeting.source_filename, meeting.source_bytes
        await jobs.update(
            session, org_id=org_id, job_id=job_id, status="running", step="transcribe", progress=0.1
        )
        await session.commit()

    try:
        segments = label_speakers(await stt.transcribe(filename, data))
    except STTError as e:
        await safe_fail(sm, org_id=org_id, meeting_id=meeting_id, job_id=job_id, error=str(e))
        return
    except asyncio.CancelledError:
        # arq job_timeout / abort: record the interruption, then let the cancellation propagate.
        log.warning("transcription of meeting %s was cancelled", meeting_id)
        await safe_fail(
            sm, org_id=org_id, meeting_id=meeting_id, job_id=job_id,
            error="Chuyển giọng nói bị gián đoạn hoặc quá thời gian",
        )
        raise
    except Exception:
        log.exception("unexpected error transcribing meeting %s", meeting_id)
        await safe_fail(
            sm, org_id=org_id, meeting_id=meeting_id, job_id=job_id,
            error="Lỗi không mong muốn khi chuyển giọng nói",
        )
        return
    if not segments:
        await safe_fail(sm, org_id=org_id, meeting_id=meeting_id, job_id=job_id, error=NO_SPEECH)
        return

    # The audio is replaced by the generated transcript: analysis and re-analysis read it as usual.
    async with sm() as session:
        await meetings.replace_source(
            session,
            org_id=org_id,
            meeting_id=meeting_id,
            filename=f"{PurePath(filename).stem or 'audio'}.txt",
            data=to_transcript_txt(segments),
        )
        await meetings.set_status(
            session, org_id=org_id, meeting_id=meeting_id, status="awaiting_speakers"
        )
        await jobs.update(
            session,
            org_id=org_id,
            job_id=job_id,
            status="succeeded",
            step="done",
            progress=1.0,
            result={"utterances": len(segments)},
        )
        await session.commit()
