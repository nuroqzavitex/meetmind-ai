from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.api_helpers import auth
from tests.backend.pipeline_helpers import seed_analyzed_meeting

from app.ai.domain.models import Hold, MeetingItem
from app.repositories import items as items_repo
from app.repositories import meetings as meetings_repo

pytestmark = pytest.mark.db


async def _items(client: httpx.AsyncClient, mid: str) -> list[dict[str, Any]]:
    r = await client.get(f"/meetings/{mid}/items", headers=auth())
    assert r.status_code == 200
    out: list[dict[str, Any]] = r.json()
    return out


async def _raw_items(
    sessionmaker: async_sessionmaker[AsyncSession], meeting_id: str = "m1", org_id: str = "org_a"
) -> list[MeetingItem]:
    async with sessionmaker() as s:
        rows = await items_repo.list_for_meeting(s, org_id=org_id, meeting_id=meeting_id)
    return [items_repo.to_model(r) for r in rows]


async def test_items_flagged_first(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    items = await _items(client, mid)
    assert items
    first_clean = next((i for i, it in enumerate(items) if not it["flags"]), len(items))
    assert all(it["flags"] for it in items[:first_clean])
    groups = [0 if "low_confidence" in it["flags"] else 1 if it["flags"] else 2 for it in items]
    assert groups == sorted(groups)
    rows = await _raw_items(sessionmaker)
    expected = sorted(rows, key=lambda m: 0 if "low_confidence" in m.flags else 1 if m.flags else 2)
    assert [it["id"] for it in items] == [m.id for m in expected]


async def test_approve_and_reject_record_events(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    items = await _items(client, mid)
    a, b = items[0]["id"], items[1]["id"]
    r = await client.patch(f"/items/{a}", json={"action": "approve"}, headers=auth())
    assert r.status_code == 200 and r.json()["review_state"] == "approved"
    r = await client.patch(f"/items/{b}", json={"action": "reject"}, headers=auth())
    assert r.status_code == 200 and r.json()["review_state"] == "rejected"
    ev = (await client.get(f"/items/{a}/events", headers=auth())).json()
    assert [e["action"] for e in ev] == ["created", "approved"]
    assert ev[-1]["actor_name"] == "Lan"
    assert set(ev[-1]) == {"action", "actor_name", "reason", "created_at"}
    ev_b = (await client.get(f"/items/{b}/events", headers=auth())).json()
    assert ev_b[-1]["action"] == "rejected"


async def test_edit_action_item_clears_satisfied_flag(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    item = next(
        i
        for i in await _items(client, mid)
        if i["type"] == "action_item" and "missing_due_date" in i["flags"]
    )
    async with sessionmaker() as s:
        row = await items_repo.get(s, org_id="org_a", item_id=item["id"])
        assert row is not None
        model = items_repo.to_model(row)
        model = model.model_copy(update={"flags": [*model.flags, "low_confidence"]})
        await items_repo.save(s, item=row, model=model)
        await s.commit()
    r = await client.patch(
        f"/items/{item['id']}",
        json={"action": "edit", "patch": {"due_date": "2026-10-20"}},
        headers=auth(),
    )
    assert r.status_code == 200
    body = r.json()
    assert "missing_due_date" not in body["flags"]
    assert "low_confidence" in body["flags"]
    assert body["review_state"] == "edited" and body["due_date"] == "2026-10-20"
    async with sessionmaker() as s:
        events = await items_repo.events(s, org_id="org_a", item_id=item["id"])
    edited = events[-1]
    assert edited.action == "edited"
    assert edited.before is not None and edited.before["due_date"] is None
    assert edited.after is not None and edited.after["due_date"] == "2026-10-20"


async def test_decision_change_needs_reason(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    dec = next(i for i in await _items(client, mid) if i["type"] == "decision")
    payload = {"action": "edit", "patch": {"content": "Dùng MySQL"}}
    r = await client.patch(f"/items/{dec['id']}", json=payload, headers=auth())
    assert r.status_code == 422 and r.json()["error"]["code"] == "reason_required"
    r = await client.patch(
        f"/items/{dec['id']}", json={**payload, "reason": "Đổi ý"}, headers=auth()
    )
    assert r.status_code == 200 and r.json()["content"] == "Dùng MySQL"
    r = await client.patch(f"/items/{dec['id']}", json=payload, headers=auth())
    assert r.status_code == 200


async def test_patch_rejects_unknown_fields(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    iid = (await _items(client, mid))[0]["id"]
    r = await client.patch(
        f"/items/{iid}", json={"action": "edit", "patch": {"evidence": []}}, headers=auth()
    )
    assert r.status_code == 422


async def test_edit_requires_patch(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    iid = (await _items(client, mid))[0]["id"]
    r = await client.patch(f"/items/{iid}", json={"action": "edit"}, headers=auth())
    assert r.status_code == 422 and r.json()["error"]["code"] == "patch_required"


async def test_approve_clean_counts_only_clean_pending(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    items = await _items(client, mid)
    clean = [i for i in items if not i["flags"]]
    r = await client.post(f"/meetings/{mid}/items/approve-clean", headers=auth())
    assert r.status_code == 200 and r.json() == {"approved": len(clean)}
    after = await _items(client, mid)
    assert all(i["review_state"] == "approved" for i in after if not i["flags"])
    assert all(i["review_state"] == "pending" for i in after if i["flags"])
    r = await client.post(f"/meetings/{mid}/items/approve-clean", headers=auth())
    assert r.json() == {"approved": 0}


async def test_review_blocked_when_not_in_review(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    iid = (await _items(client, mid))[0]["id"]
    async with sessionmaker() as s:
        await meetings_repo.set_status(s, org_id="org_a", meeting_id=mid, status="analyzing")
        await s.commit()
    r = await client.patch(f"/items/{iid}", json={"action": "approve"}, headers=auth())
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_in_review"
    r = await client.post(f"/meetings/{mid}/items/approve-clean", headers=auth())
    assert r.status_code == 409


async def test_cross_org_is_404(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await seed_analyzed_meeting(sessionmaker, "org_a", "ma")
    await seed_analyzed_meeting(sessionmaker, "org_b", "mb")
    b_items = await _raw_items(sessionmaker, "mb", "org_b")
    iid = b_items[0].id
    other = auth(org="org_a")
    assert (await client.get("/meetings/mb/items", headers=other)).status_code == 404
    assert (await client.get("/meetings/mb/topics", headers=other)).status_code == 404
    r = await client.patch(f"/items/{iid}", json={"action": "approve"}, headers=other)
    assert r.status_code == 404
    assert (await client.get(f"/items/{iid}/events", headers=other)).status_code == 404
    assert (
        await client.post("/meetings/mb/items/approve-clean", headers=other)
    ).status_code == 404
    after = await _raw_items(sessionmaker, "mb", "org_b")
    assert [m.review_state for m in after] == [m.review_state for m in b_items]
    async with sessionmaker() as s:
        events = await items_repo.events(s, org_id="org_b", item_id=iid)
    assert [e.action for e in events] == ["created"]


async def test_topics_endpoint(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    r = await client.get(f"/meetings/{mid}/topics", headers=auth())
    assert r.status_code == 200
    topic = next(t for t in r.json() if "Postgres" in t["options"])
    assert topic["options"]["Postgres"]["state"] == "decided"
    assert topic["options"]["MongoDB"]["state"] == "superseded"


async def _hold_first(
    sessionmaker: async_sessionmaker[AsyncSession], item_type: str
) -> str:
    """Put a guard hold on the first item of `item_type`, as the analysis would; return its id."""
    hold = Hold(reason="declined", quote="Tuần này em kín lịch rồi.", phrase="kín lịch",
                speaker="Minh", ts="00:04:20")
    async with sessionmaker() as s:
        rows = await items_repo.list_for_meeting(s, org_id="org_a", meeting_id="m1")
        row = next(r for r in rows if r.type == item_type)
        model = items_repo.to_model(row)
        held = model.model_copy(update={
            "hold": hold, "flags": [*model.flags, "needs_confirmation", "declined"]})
        await items_repo.save(s, item=row, model=held)
        await s.commit()
        return row.id


async def test_approving_a_held_item_makes_it_official(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await seed_analyzed_meeting(sessionmaker)
    iid = await _hold_first(sessionmaker, "action_item")
    r = await client.patch(f"/items/{iid}", json={"action": "approve"}, headers=auth())
    body = r.json()
    assert r.status_code == 200 and body["review_state"] == "approved"
    assert body["hold"] is None
    assert "needs_confirmation" not in body["flags"] and "declined" not in body["flags"]


async def test_held_task_becomes_an_open_question(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await seed_analyzed_meeting(sessionmaker)
    iid = await _hold_first(sessionmaker, "action_item")
    r = await client.patch(f"/items/{iid}", json={"action": "to_question"}, headers=auth())
    body = r.json()
    assert r.status_code == 200
    assert body["type"] == "open_question" and body["status"] == "open"
    assert body["review_state"] == "edited" and body["due_date"] is None
    assert body["hold"]["reason"] == "declined"  # kept: it explains why the question is open
    assert "needs_confirmation" not in body["flags"]
    ev = (await client.get(f"/items/{iid}/events", headers=auth())).json()
    assert ev[-1]["action"] == "to_question"


async def test_held_decision_becomes_its_question(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await seed_analyzed_meeting(sessionmaker)
    iid = await _hold_first(sessionmaker, "decision")
    before = next(i for i in await _items(client, "m1") if i["id"] == iid)
    r = await client.patch(f"/items/{iid}", json={"action": "to_question"}, headers=auth())
    assert r.json()["content"] == before["content"].rsplit("→", 1)[0].strip()


async def test_only_decisions_and_tasks_convert_to_questions(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    other = next(i for i in await _items(client, mid)
                 if i["type"] not in ("decision", "action_item"))
    r = await client.patch(f"/items/{other['id']}", json={"action": "to_question"}, headers=auth())
    assert r.status_code == 422 and r.json()["error"]["code"] == "not_convertible"
