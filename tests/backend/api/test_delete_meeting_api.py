import json
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.api_helpers import auth
from tests.backend.pipeline_helpers import seed_analyzed_meeting

from app.core.config import STALE_JOB_SECONDS
from app.models import Item, ItemEvent, Job, Meeting, TranscriptChunk, Utterance

pytestmark = pytest.mark.db

CTX = {"title": "Chốt CSDL", "meeting_date": "2026-10-01"}


async def _publish(client: httpx.AsyncClient, mid: str) -> None:
    for it in (await client.get(f"/meetings/{mid}/items", headers=auth())).json():
        r = await client.patch(f"/items/{it['id']}", json={"action": "approve"}, headers=auth())
        assert r.status_code == 200
    assert (await client.post(f"/meetings/{mid}/publish", headers=auth())).status_code == 200


async def _count(sm: async_sessionmaker[AsyncSession], model: type, mid: str) -> int:
    async with sm() as s:
        col = model.id if model is Meeting else model.meeting_id  # type: ignore[attr-defined]
        return len((await s.scalars(select(col).where(col == mid))).all())


async def test_admin_deletes_published_meeting_and_everything_under_it(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    await _publish(client, mid)
    async with sessionmaker() as s:
        assert (await s.scalar(select(func.count()).select_from(ItemEvent))) > 0
    r = await client.delete(f"/meetings/{mid}", headers=auth())
    assert r.status_code == 204
    assert (await client.get(f"/meetings/{mid}", headers=auth())).status_code == 404
    assert (await client.get("/meetings", headers=auth())).json() == []
    for model in (Meeting, Item, Utterance, Job, TranscriptChunk):
        assert await _count(sessionmaker, model, mid) == 0, model.__name__
    async with sessionmaker() as s:
        assert (await s.scalar(select(func.count()).select_from(ItemEvent))) == 0
    again = await client.delete(f"/meetings/{mid}", headers=auth())
    assert again.status_code == 404


async def test_members_cannot_delete(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    r = await client.delete(f"/meetings/{mid}", headers=auth(user="m1", role="member"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "admin_only"
    assert (await client.get(f"/meetings/{mid}", headers=auth())).status_code == 200


async def test_meeting_being_analyzed_cannot_be_deleted_until_its_job_is_stale(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession],
    transcript_bytes: bytes,
) -> None:
    r = await client.post(
        "/meetings",
        files={"file": ("t.txt", transcript_bytes)},
        data={"context": json.dumps(CTX)},
        headers=auth(),
    )
    mid, jid = r.json()["meeting_id"], r.json()["job_id"]
    busy = await client.delete(f"/meetings/{mid}", headers=auth())
    assert busy.status_code == 409 and busy.json()["error"]["code"] == "job_running"

    async with sessionmaker() as s:  # the worker died: the job never moves again
        await s.execute(
            update(Job).where(Job.id == jid)
            .values(updated_at=func.now() - timedelta(seconds=STALE_JOB_SECONDS + 60))
        )
        await s.commit()
    assert (await client.delete(f"/meetings/{mid}", headers=auth())).status_code == 204


async def test_failed_meeting_can_be_deleted(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    async with sessionmaker() as s:
        await s.execute(update(Meeting).where(Meeting.id == mid).values(status="failed"))
        await s.commit()
    assert (await client.delete(f"/meetings/{mid}", headers=auth())).status_code == 204
