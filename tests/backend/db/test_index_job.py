import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.pipeline_helpers import seed_analyzed_meeting

from app.ai.retrieval.embedder import HashEmbedder
from app.models import Item, TranscriptChunk
from app.repositories import jobs, meetings
from app.services.indexing import run_index

pytestmark = pytest.mark.db
ORG = "org_a"


class BoomEmbedder:
    dim = 1024

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("boom")


async def _published(sm: async_sessionmaker[AsyncSession]) -> None:
    await seed_analyzed_meeting(sm)
    async with sm() as s:
        await s.execute(update(Item).where(Item.meeting_id == "m1").values(review_state="approved"))
        await meetings.set_status(s, org_id=ORG, meeting_id="m1", status="published")
        await s.commit()


async def _job(sm: async_sessionmaker[AsyncSession]) -> str:
    async with sm() as s:
        job = await jobs.create(s, org_id=ORG, meeting_id="m1", kind="index")
        await s.commit()
        return job.id


async def test_index_job_embeds_items_and_chunks(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await _published(sessionmaker)
    job_id = await _job(sessionmaker)
    await run_index(sessionmaker, HashEmbedder(1024), org_id=ORG, meeting_id="m1", job_id=job_id)
    async with sessionmaker() as s:
        job = await jobs.get(s, org_id=ORG, job_id=job_id)
        rows = list((await s.scalars(select(Item).where(Item.meeting_id == "m1"))).all())
        n_chunks = await s.scalar(select(func.count()).select_from(TranscriptChunk))
        assert job is not None and job.status == "succeeded"
        assert job.result == {"items": len(rows), "chunks": 4}
        assert rows and n_chunks == 4
        for r in rows:
            assert r.indexed_at is not None and r.search_text
            assert r.embedding is not None and len(r.embedding) == 1024
        stamps = {r.id: r.indexed_at for r in rows}

    job2 = await _job(sessionmaker)
    await run_index(sessionmaker, HashEmbedder(1024), org_id=ORG, meeting_id="m1", job_id=job2)
    async with sessionmaker() as s:
        again = await jobs.get(s, org_id=ORG, job_id=job2)
        assert again is not None and again.result == {"items": 0, "chunks": 0}
        rows = list((await s.scalars(select(Item).where(Item.meeting_id == "m1"))).all())
        assert {r.id: r.indexed_at for r in rows} == stamps
        assert await s.scalar(select(func.count()).select_from(TranscriptChunk)) == 4


async def test_index_job_failure_keeps_meeting_published(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await _published(sessionmaker)
    job_id = await _job(sessionmaker)
    await run_index(sessionmaker, BoomEmbedder(), org_id=ORG, meeting_id="m1", job_id=job_id)
    async with sessionmaker() as s:
        job = await jobs.get(s, org_id=ORG, job_id=job_id)
        meeting = await meetings.get(s, org_id=ORG, meeting_id="m1")
        assert job is not None and job.status == "failed"
        assert job.error is not None and job.error.startswith("Lập chỉ mục lỗi")
        assert meeting is not None and meeting.status == "published"


async def test_index_skips_unpublished_meeting(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await seed_analyzed_meeting(sessionmaker)
    job_id = await _job(sessionmaker)
    await run_index(sessionmaker, HashEmbedder(1024), org_id=ORG, meeting_id="m1", job_id=job_id)
    async with sessionmaker() as s:
        job = await jobs.get(s, org_id=ORG, job_id=job_id)
        assert job is not None and job.status == "succeeded"
        assert job.result == {"items": 0, "chunks": 0}
