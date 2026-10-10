import asyncio
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.pipeline_helpers import fake_from_fixtures, fx, seed_meeting

from app.ai.config import AISettings
from app.ai.llm.fake import FakeLLM
from app.models import Meeting
from app.repositories import items, jobs, meetings
from app.services import analysis as analysis_service
from app.services.analysis import run_analysis
from app.workers import main as worker

pytestmark = pytest.mark.db
ORG = "org_a"
AI = AISettings()


async def _run(sm: async_sessionmaker[AsyncSession], llm: Any, job_id: str) -> None:
    await run_analysis(sm, llm, AI, org_id=ORG, meeting_id="m1", job_id=job_id)


async def test_analysis_persists_results(sessionmaker: async_sessionmaker[AsyncSession]):
    job_id = await seed_meeting(sessionmaker)
    await _run(sessionmaker, fake_from_fixtures(), job_id)
    async with sessionmaker() as s:
        job = await jobs.get(s, org_id=ORG, job_id=job_id)
        assert job is not None and job.status == "succeeded" and job.progress == 1.0
        meeting = await meetings.get(s, org_id=ORG, meeting_id="m1")
        assert meeting is not None and meeting.status == "in_review"
        assert len(await meetings.get_utterances(s, org_id=ORG, meeting_id="m1")) == 16
        assert await meetings.get_topics(s, org_id=ORG, meeting_id="m1")
        rows = await items.list_for_meeting(s, org_id=ORG, meeting_id="m1")
        assert job.result == {"items": len(rows)}
        decisions = [r for r in rows if r.type == "decision"]
        assert len(decisions) == 1 and "Postgres" in decisions[0].data["content"]
        for r in rows:
            evs = await items.events(s, org_id=ORG, item_id=r.id)
            assert [e.action for e in evs] == ["created"]
            assert evs[0].actor_id == "system" and evs[0].before is None


async def test_progress_is_visible_during_run(sessionmaker: async_sessionmaker[AsyncSession]):
    job_id = await seed_meeting(sessionmaker)
    seen: list[tuple[str | None, float]] = []
    inner = fake_from_fixtures()

    class Spy:
        async def structured(self, *, agent: str, system: str, user: str, schema: Any) -> Any:
            if agent == "topics":
                async with sessionmaker() as s:
                    j = await jobs.get(s, org_id=ORG, job_id=job_id)
                    assert j is not None
                    seen.append((j.step, j.progress))
            return await inner.structured(agent=agent, system=system, user=user, schema=schema)

    await _run(sessionmaker, Spy(), job_id)
    assert seen and seen[0][0] in {"topics", "state_machine", "check_quotes", "extract"}
    assert seen[0][1] >= 0.2


async def test_llm_failure_marks_failed(sessionmaker: async_sessionmaker[AsyncSession]):
    job_id = await seed_meeting(sessionmaker)
    await _run(sessionmaker, FakeLLM({"extract": [fx("extract.json")]}), job_id)
    async with sessionmaker() as s:
        job = await jobs.get(s, org_id=ORG, job_id=job_id)
        assert job is not None and job.status == "failed" and job.step == "topics"
        assert job.error is not None and job.error.startswith("Bước topics lỗi")
        meeting = await meetings.get(s, org_id=ORG, meeting_id="m1")
        assert meeting is not None and meeting.status == "failed"
        assert await items.list_for_meeting(s, org_id=ORG, meeting_id="m1") == []


async def test_reanalyze_after_failure_does_not_duplicate(
    sessionmaker: async_sessionmaker[AsyncSession],
):
    job_id = await seed_meeting(sessionmaker)
    await _run(sessionmaker, FakeLLM({"extract": [fx("extract.json")]}), job_id)
    async with sessionmaker() as s:
        job2 = await jobs.create(s, org_id=ORG, meeting_id="m1", kind="analyze")
        await meetings.set_status(s, org_id=ORG, meeting_id="m1", status="analyzing")
        await s.commit()
        job2_id = job2.id
    await _run(sessionmaker, fake_from_fixtures(), job2_id)
    ref_id = await seed_meeting(sessionmaker, meeting_id="m2")
    await run_analysis(sessionmaker, fake_from_fixtures(), AI, org_id=ORG, meeting_id="m2",
                       job_id=ref_id)
    async with sessionmaker() as s:
        a = await items.list_for_meeting(s, org_id=ORG, meeting_id="m1")
        b = await items.list_for_meeting(s, org_id=ORG, meeting_id="m2")
        assert len(a) == len(b) > 0
        ua = await meetings.get_utterances(s, org_id=ORG, meeting_id="m1")
        ub = await meetings.get_utterances(s, org_id=ORG, meeting_id="m2")
        assert len(ua) == len(ub) == 16


async def test_non_queued_job_is_skipped(sessionmaker: async_sessionmaker[AsyncSession]):
    job_id = await seed_meeting(sessionmaker)
    await _run(sessionmaker, fake_from_fixtures(), job_id)
    llm = fake_from_fixtures()
    await _run(sessionmaker, llm, job_id)
    assert llm.calls == []


async def test_worker_function_delegates(sessionmaker: async_sessionmaker[AsyncSession]):
    job_id = await seed_meeting(sessionmaker)
    await worker.analyze(
        {"sessionmaker": sessionmaker, "llm": fake_from_fixtures(), "ai": AI},
        org_id=ORG, meeting_id="m1", job_id=job_id,
    )
    async with sessionmaker() as s:
        job = await jobs.get(s, org_id=ORG, job_id=job_id)
        assert job is not None and job.status == "succeeded"


async def test_cancellation_marks_job_and_meeting_failed(
    sessionmaker: async_sessionmaker[AsyncSession],
):
    job_id = await seed_meeting(sessionmaker)
    started = asyncio.Event()

    class Hang:
        async def structured(self, *, agent: str, system: str, user: str, schema: Any) -> Any:
            started.set()
            await asyncio.sleep(3600)

    task = asyncio.create_task(_run(sessionmaker, Hang(), job_id))
    await asyncio.wait_for(started.wait(), 10)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with sessionmaker() as s:
        job = await jobs.get(s, org_id=ORG, job_id=job_id)
        assert job is not None and job.status == "failed"
        assert job.error == "Phân tích bị gián đoạn hoặc quá thời gian"
        meeting = await meetings.get(s, org_id=ORG, meeting_id="m1")
        assert meeting is not None and meeting.status == "failed"


async def test_corrupt_context_marks_failed(sessionmaker: async_sessionmaker[AsyncSession]):
    job_id = await seed_meeting(sessionmaker)
    async with sessionmaker() as s:
        await s.execute(update(Meeting).where(Meeting.id == "m1").values(context={"bad": 1}))
        await s.commit()
    await _run(sessionmaker, fake_from_fixtures(), job_id)
    async with sessionmaker() as s:
        job = await jobs.get(s, org_id=ORG, job_id=job_id)
        assert job is not None and job.status == "failed"
        meeting = await meetings.get(s, org_id=ORG, meeting_id="m1")
        assert meeting is not None and meeting.status == "failed"


async def test_failing_fail_handler_never_masks(
    sessionmaker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
):
    job_id = await seed_meeting(sessionmaker)

    async def boom(*_: Any, **__: Any) -> None:
        raise ConnectionError("db gone")

    monkeypatch.setattr(analysis_service, "_fail", boom)
    await _run(sessionmaker, FakeLLM({"extract": [fx("extract.json")]}), job_id)  # no raise
