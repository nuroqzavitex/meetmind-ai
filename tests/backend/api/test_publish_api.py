import json

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.api_helpers import auth
from tests.backend.pipeline_helpers import seed_analyzed_meeting

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
