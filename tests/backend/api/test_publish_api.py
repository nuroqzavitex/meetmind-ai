import json

import httpx
import pytest
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.api_helpers import FakeQueue, auth
from tests.backend.pipeline_helpers import seed_analyzed_meeting

from app.models import Item
from app.repositories import items as items_repo
from app.repositories import jobs

pytestmark = pytest.mark.db


async def _approve_all(client: httpx.AsyncClient, mid: str) -> list[str]:
    items = (await client.get(f"/meetings/{mid}/items", headers=auth())).json()
    for it in items:
        r = await client.patch(f"/items/{it['id']}", json={"action": "approve"}, headers=auth())
        assert r.status_code == 200
    return [it["id"] for it in items]


async def test_publish_blocked_by_pending_items(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    r = await client.post(f"/meetings/{mid}/publish", headers=auth())
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "pending_items"
    n = len((await client.get(f"/meetings/{mid}/items", headers=auth())).json())
    assert f"Còn {n} mục chưa duyệt" in err["message"]


async def test_publish_blocked_by_running_job(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    await _approve_all(client, mid)
    async with sessionmaker() as s:
        await jobs.create(s, org_id="org_a", meeting_id=mid, kind="analyze")
        await s.commit()
    r = await client.post(f"/meetings/{mid}/publish", headers=auth())
    assert r.status_code == 409 and r.json()["error"]["code"] == "job_running"


async def test_publish_then_export(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    await _approve_all(client, mid)
    r = await client.post(f"/meetings/{mid}/publish", headers=auth())
    assert r.status_code == 200 and r.json()["status"] == "published"
    assert r.json()["published_at"] is not None
    again = await client.post(f"/meetings/{mid}/publish", headers=auth())
    assert again.status_code == 409 and again.json()["error"]["code"] == "not_in_review"

    md = await client.get(f"/meetings/{mid}/export", params={"format": "md"}, headers=auth())
    assert md.status_code == 200
    assert md.headers["content-type"].startswith("text/markdown")
    disp = md.headers["content-disposition"]
    assert disp.startswith("attachment") and '.md"' in disp
    assert "PostgreSQL" in md.text or "Postgres" in md.text

    js = await client.get(f"/meetings/{mid}/export", params={"format": "json"}, headers=auth())
    assert js.status_code == 200
    assert js.headers["content-type"].startswith("application/json")
    assert "items" in json.loads(js.content)

    bad = await client.get(f"/meetings/{mid}/export", params={"format": "pdf"}, headers=auth())
    assert bad.status_code == 422


async def test_export_before_publish_409(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    r = await client.get(f"/meetings/{mid}/export", params={"format": "md"}, headers=auth())
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_published"


async def test_report_and_reopen_flow(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    ids = await _approve_all(client, mid)
    assert (await client.post(f"/meetings/{mid}/publish", headers=auth())).status_code == 200
    iid = ids[0]

    empty = await client.post(f"/items/{iid}/report", json={"reason": ""}, headers=auth())
    assert empty.status_code == 422
    r = await client.post(f"/items/{iid}/report", json={"reason": "Sai hạn"}, headers=auth())
    assert r.status_code == 204
    async with sessionmaker() as s:
        evs = await items_repo.events(s, org_id="org_a", item_id=iid)
    assert evs[-1].action == "reported" and evs[-1].reason == "Sai hạn"

    r = await client.patch(f"/items/{iid}", json={"action": "approve"}, headers=auth())
    assert r.status_code == 409

    r = await client.post(f"/items/{iid}/reopen", json={"reason": "Sửa"}, headers=auth())
    assert r.status_code == 200 and r.json()["review_state"] == "pending"
    meeting = (await client.get(f"/meetings/{mid}", headers=auth())).json()
    assert meeting["status"] == "in_review" and meeting["published_at"] is not None

    r = await client.patch(
        f"/items/{iid}",
        json={"action": "edit", "patch": {"rationale": "đã sửa"}, "reason": "Sửa"},
        headers=auth(),
    )
    assert r.status_code == 200
    r = await client.patch(f"/items/{iid}", json={"action": "approve"}, headers=auth())
    assert r.status_code == 200
    assert (await client.post(f"/meetings/{mid}/publish", headers=auth())).status_code == 200


async def test_publish_enqueues_index_job(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession], queue: FakeQueue
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    await _approve_all(client, mid)
    assert (await client.post(f"/meetings/{mid}/publish", headers=auth())).status_code == 200
    kind, org, meeting, job_id = queue.calls[-1]
    assert (kind, org, meeting) == ("index", "org_a", mid)
    async with sessionmaker() as s:
        job = await jobs.get(s, org_id="org_a", job_id=job_id)
    assert job is not None and job.kind == "index" and job.status == "queued"


async def test_publish_succeeds_when_index_enqueue_fails(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession], queue: FakeQueue
) -> None:
    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("redis down")

    queue.enqueue = boom  # type: ignore[method-assign]
    mid = await seed_analyzed_meeting(sessionmaker)
    await _approve_all(client, mid)
    r = await client.post(f"/meetings/{mid}/publish", headers=auth())
    assert r.status_code == 200 and r.json()["status"] == "published"
    async with sessionmaker() as s:
        job = await jobs.latest_for_meeting(
            s, org_id="org_a", meeting_id=mid, kind="index"
        )
    assert job is not None and job.kind == "index" and job.status == "failed"
    assert job.error == "Không đưa được job vào hàng đợi"


async def test_reopen_clears_index_and_republish_reindexes(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession], queue: FakeQueue
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    ids = await _approve_all(client, mid)
    assert (await client.post(f"/meetings/{mid}/publish", headers=auth())).status_code == 200
    iid = ids[0]
    async with sessionmaker() as s:
        await s.execute(
            update(Item)
            .where(Item.id == iid)
            .values(search_text="x", embedding=[0.1] * 1024, indexed_at=func.now())
        )
        await s.commit()
    r = await client.post(f"/items/{iid}/reopen", json={}, headers=auth())
    assert r.status_code == 200
    async with sessionmaker() as s:
        row = await items_repo.get(s, org_id="org_a", item_id=iid)
    assert row is not None
    assert row.indexed_at is None and row.embedding is None and row.search_text is None

    before = len(queue.calls)
    r = await client.patch(f"/items/{iid}", json={"action": "approve"}, headers=auth())
    assert r.status_code == 200
    assert (await client.post(f"/meetings/{mid}/publish", headers=auth())).status_code == 200
    assert len(queue.calls) == before + 1 and queue.calls[-1][0] == "index"


async def test_edit_and_republish_reindexes_only_changed_items(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession], queue: FakeQueue
) -> None:
    from sqlalchemy import select
    from tests.backend.pipeline_helpers import seed_published_indexed_meeting

    from app.ai.retrieval.embedder import HashEmbedder
    from app.services.indexing import run_index

    emb = HashEmbedder(1024)
    mid = await seed_published_indexed_meeting(sessionmaker, emb)
    async with sessionmaker() as s:
        rows = list((await s.scalars(select(Item).where(Item.meeting_id == mid))).all())
        stamps = {r.id: r.indexed_at for r in rows}
    assert len(rows) >= 3 and all(v is not None for v in stamps.values())
    a, b = rows[0].id, rows[1].id

    assert (await client.post(f"/items/{a}/reopen", json={}, headers=auth())).status_code == 200
    r = await client.patch(
        f"/items/{b}",
        json={"action": "edit", "patch": {"content": "Nội dung đã sửa hoàn toàn"}, "reason": "Sửa"},
        headers=auth(),
    )
    assert r.status_code == 200
    async with sessionmaker() as s:
        row_b = await items_repo.get(s, org_id="org_a", item_id=b)
        assert row_b is not None and row_b.search_text is None and row_b.indexed_at is None
    assert (
        await client.patch(f"/items/{a}", json={"action": "approve"}, headers=auth())
    ).status_code == 200
    assert (await client.post(f"/meetings/{mid}/publish", headers=auth())).status_code == 200
    job_id = queue.calls[-1][3]
    await run_index(sessionmaker, emb, org_id="org_a", meeting_id=mid, job_id=job_id)

    async with sessionmaker() as s:
        after = {r.id: r for r in (await s.scalars(select(Item).where(Item.meeting_id == mid)))}
        job = await jobs.get(s, org_id="org_a", job_id=job_id)
    assert job is not None and job.result is not None and job.result["items"] == 2
    assert "Nội dung đã sửa hoàn toàn" in (after[b].search_text or "")
    for iid, row in after.items():
        assert row.indexed_at is not None
        if iid in (a, b):
            assert row.indexed_at != stamps[iid]
        else:
            assert row.indexed_at == stamps[iid]


async def test_publish_succeeds_when_index_job_creation_fails(
    client: httpx.AsyncClient,
    sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("db hiccup")

    mid = await seed_analyzed_meeting(sessionmaker)
    await _approve_all(client, mid)
    monkeypatch.setattr(jobs, "create", boom)
    r = await client.post(f"/meetings/{mid}/publish", headers=auth())
    assert r.status_code == 200 and r.json()["status"] == "published"
