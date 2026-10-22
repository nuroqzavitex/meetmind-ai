import json
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.api_helpers import auth
from tests.backend.pipeline_helpers import seed_analyzed_meeting

from app.models import Meeting
from app.notify.discord import DiscordClient

pytestmark = pytest.mark.db

HOOK = "https://discord.com/api/webhooks/1/tok"


async def _publish(client: httpx.AsyncClient, mid: str = "m1") -> None:
    for it in (await client.get(f"/meetings/{mid}/items", headers=auth())).json():
        r = await client.patch(f"/items/{it['id']}", json={"action": "approve"}, headers=auth())
        assert r.status_code == 200
    assert (await client.post(f"/meetings/{mid}/publish", headers=auth())).status_code == 200


async def _published(
    client: httpx.AsyncClient, sm: async_sessionmaker[AsyncSession], project: str = "Thanh toán"
) -> None:
    await seed_analyzed_meeting(sm)
    async with sm() as s:
        await s.execute(update(Meeting).where(Meeting.id == "m1").values(project=project))
        await s.commit()
    await _publish(client)


async def test_only_published_meetings_count(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await seed_analyzed_meeting(sessionmaker)  # still in review
    body = (await client.get("/overview/decisions", headers=auth())).json()
    assert body == {"projects": [], "decisions": []}


async def test_decisions_tasks_and_agenda_from_published_minutes(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _published(client, sessionmaker)
    d = (await client.get("/overview/decisions", headers=auth())).json()
    assert d["projects"] == ["Thanh toán"]
    final = [e for e in d["decisions"] if e["status"] == "final"]
    assert final and "Postgre" in final[0]["content"]
    assert final[0]["meeting_title"] and final[0]["quote"] and final[0]["utterance_id"]

    t = (await client.get("/overview/tasks", headers=auth())).json()
    assert t["tasks"] and "Minh" in t["owners"]
    minh = (await client.get("/overview/tasks?owner=minh", headers=auth())).json()
    assert minh["tasks"] and all(e["owner"] == "Minh" for e in minh["tasks"])

    a = (await client.get("/overview/agenda?project=Thanh toán", headers=auth())).json()
    assert a["project"] == "Thanh toán" and a["markdown"].startswith("**📋 Chương trình họp kế tiếp")
    other = (await client.get("/overview/agenda?project=Khác", headers=auth())).json()
    assert other["to_decide"] == [] and other["due"] == []


async def test_send_agenda_to_discord(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession], app: FastAPI
) -> None:
    sent: list[dict[str, Any]] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(204)

    app.state.discord = DiscordClient(httpx.MockTransport(record))
    await _published(client, sessionmaker)
    r = await client.post("/overview/agenda/discord", headers=auth())
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_webhook"
    await client.put("/settings/discord", json={"webhook_url": HOOK, "digest_enabled": False},
                     headers=auth())
    sent.clear()  # saving the webhook posts a "connected" message
    member = auth(user="m1", role="member")  # any member may post the agenda
    r = await client.post("/overview/agenda/discord", headers=member)
    assert r.status_code == 200 and r.json() == {"sent": True}
    assert sent[-1]["content"].startswith("**📋 Chương trình họp kế tiếp")
    assert sent[-1]["allowed_mentions"] == {"parse": []}
