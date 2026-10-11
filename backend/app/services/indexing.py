"""Index a published meeting: embed approved items and transcript chunks."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.domain.models import MeetingItem
from app.ai.retrieval.embedder import Embedder
from app.ai.retrieval.indexing import item_search_text, make_transcript_chunks
from app.repositories import jobs, meetings, retrieval

log = logging.getLogger(__name__)

BATCH = 32


async def _embed_all(embedder: Embedder, texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        out.extend(await embedder.embed(texts[i : i + BATCH]))
    return out


async def _safe_fail(
    sm: async_sessionmaker[AsyncSession], *, org_id: str, job_id: str, error: str
) -> None:
    try:
        async with sm() as session:
            await jobs.update(session, org_id=org_id, job_id=job_id, status="failed", error=error)
            await session.commit()
    except Exception:
        log.exception("could not mark index job %s as failed", job_id)


async def _index(
    sm: async_sessionmaker[AsyncSession], embedder: Embedder, *, org_id: str, meeting_id: str
) -> dict[str, int]:
    skipped = {"items": 0, "chunks": 0}
    async with sm() as session:
        meeting = await meetings.get(session, org_id=org_id, meeting_id=meeting_id)
        if meeting is None or meeting.status != "published":
            return skipped
        item_ids: list[str] = []
        texts: list[str] = []
        for r in await retrieval.indexable_items(session, org_id=org_id, meeting_id=meeting_id):
            text = item_search_text(MeetingItem.model_validate(r.data))
            if r.indexed_at is None or r.search_text != text:
                item_ids.append(r.id)
                texts.append(text)
        need_chunks = not await retrieval.has_chunks(
            session, org_id=org_id, meeting_id=meeting_id
        )
        utterances = (
            await meetings.get_utterances(session, org_id=org_id, meeting_id=meeting_id)
            if need_chunks
            else []
        )
    chunks = make_transcript_chunks(utterances)
    item_vecs = await _embed_all(embedder, texts)
    chunk_vecs = await _embed_all(embedder, [c.text for c in chunks])

    async with sm() as session:
        meeting = await meetings.get(session, org_id=org_id, meeting_id=meeting_id)
        if meeting is None or meeting.status != "published":
            return skipped
        by_id = {
            r.id: r
            for r in await retrieval.indexable_items(session, org_id=org_id, meeting_id=meeting_id)
        }
        done = 0
        for item_id, text, vec in zip(item_ids, texts, item_vecs, strict=True):
            row = by_id.get(item_id)
            if row is None:
                continue
            await retrieval.set_item_index(session, item=row, search_text=text, embedding=vec)
            done += 1
        if chunks:
            await retrieval.replace_chunks(
                session,
                org_id=org_id,
                meeting_id=meeting_id,
                chunks=chunks,
                embeddings=chunk_vecs,
            )
        await session.commit()
    return {"items": done, "chunks": len(chunks)}


async def run_index(
    sm: async_sessionmaker[AsyncSession],
    embedder: Embedder,
    *,
    org_id: str,
    meeting_id: str,
    job_id: str,
) -> None:
    async with sm() as session:
        job = await jobs.get(session, org_id=org_id, job_id=job_id)
        if job is None:
            log.warning("index skipped: job %s not found", job_id)
            return
        if job.status != "queued":
            log.warning("index skipped: job %s is %s, not queued", job_id, job.status)
            return
        await jobs.update(session, org_id=org_id, job_id=job_id, status="running", step="index")
        await session.commit()
    try:
        result = await _index(sm, embedder, org_id=org_id, meeting_id=meeting_id)
        async with sm() as session:
            await jobs.update(
                session, org_id=org_id, job_id=job_id, status="succeeded", progress=1.0,
                result=result,
            )
            await session.commit()
    except asyncio.CancelledError:
        log.warning("indexing of meeting %s was cancelled", meeting_id)
        await _safe_fail(
            sm, org_id=org_id, job_id=job_id, error="Lập chỉ mục bị gián đoạn hoặc quá thời gian"
        )
        raise
    except Exception as e:
        log.exception("indexing meeting %s failed", meeting_id)
        await _safe_fail(sm, org_id=org_id, job_id=job_id, error=f"Lập chỉ mục lỗi: {e}")
