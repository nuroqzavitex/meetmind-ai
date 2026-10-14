import json
from datetime import date

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.api_helpers import FakeQueue, auth
from tests.backend.pipeline_helpers import seed_analyzed_meeting

from app.ai.domain.enums import ItemType
from app.notify.discord import DiscordClient
from app.repositories import items as items_repo
from app.services.notifications import notify_published

pytestmark = pytest.mark.db

HOOK = "https://discord.com/api/webhooks/123456/secret-token-abcd"
SECRET = "cron-test-secret"


class Recorder:
    def __init__(self, status: int = 204) -> None:
        self.status = status
        self.sent: list[tuple[str, dict[str, object]]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.sent.append((str(request.url), json.loads(request.content)))
        return httpx.Response(self.status)


@pytest.fixture
def discord(app: FastAPI) -> Recorder:
    rec = Recorder()
    app.state.discord = DiscordClient(httpx.MockTransport(rec))
    app.state.settings.cron_secret = SecretStr(SECRET)
    app.state.settings.frontend_url = "https://meetmind.test/"
    return rec


async def _configure(client: httpx.AsyncClient, org: str = "org_a", digest: bool = True) -> None:
    r = await client.put(
        "/settings/discord",
        json={"webhook_url": HOOK, "digest_enabled": digest},
        headers=auth(org=org),
    )
    assert r.status_code == 200, r.text


async def _publish(client: httpx.AsyncClient, mid: str, org: str = "org_a") -> None:
    h = auth(org=org)
    for it in (await client.get(f"/meetings/{mid}/items", headers=h)).json():
        r = await client.patch(f"/items/{it['id']}", json={"action": "approve"}, headers=h)
        assert r.status_code == 200
    assert (await client.post(f"/meetings/{mid}/publish", headers=h)).status_code == 200


async def test_settings_default_save_and_mask(client: httpx.AsyncClient, discord: Recorder) -> None:
    r = await client.get("/settings/discord", headers=auth())
    assert r.json() == {
        "configured": False, "webhook_hint": None, "digest_enabled": False, "invite_url": None
    }
    await _configure(client)
    got = (await client.get("/settings/discord", headers=auth())).json()
    assert got == {
        "configured": True, "webhook_hint": "…abcd", "digest_enabled": True, "invite_url": None
    }
    assert HOOK not in json.dumps(got)


async def test_omitted_url_keeps_it_and_empty_clears_it(
    client: httpx.AsyncClient, discord: Recorder
) -> None:
    await _configure(client)
    r = await client.put("/settings/discord", json={"digest_enabled": False}, headers=auth())
    assert r.json() == {
        "configured": True, "webhook_hint": "…abcd", "digest_enabled": False, "invite_url": None
    }
    r = await client.put(
        "/settings/discord", json={"webhook_url": "", "digest_enabled": False}, headers=auth()
    )
    assert r.json()["configured"] is False


async def test_invalid_webhook_rejected(client: httpx.AsyncClient, discord: Recorder) -> None:
    r = await client.put(
        "/settings/discord",
        json={"webhook_url": "https://evil.io/api/webhooks/1/x", "digest_enabled": True},
        headers=auth(),
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_webhook"
    assert (await client.get("/settings/discord", headers=auth())).json()["configured"] is False


async def test_send_test_message(client: httpx.AsyncClient, discord: Recorder) -> None:
    r = await client.post("/settings/discord/test", headers=auth())
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_configured"
    await _configure(client)
    assert (await client.post("/settings/discord/test", headers=auth())).status_code == 204
    url, body = discord.sent[-1]
    assert url == HOOK and body["allowed_mentions"] == {"parse": []}
    discord.status = 404
    r = await client.post("/settings/discord/test", headers=auth())
    assert r.status_code == 502 and r.json()["error"]["code"] == "discord_error"


async def test_publish_enqueues_notify_only_with_webhook(
    client: httpx.AsyncClient,
    sessionmaker: async_sessionmaker[AsyncSession],
    queue: FakeQueue,
    discord: Recorder,
) -> None:
    m1 = await seed_analyzed_meeting(sessionmaker, meeting_id="m1")
    await _publish(client, m1)
    assert [c for c in queue.calls if c[0] == "notify"] == []

    await _configure(client)
    m2 = await seed_analyzed_meeting(sessionmaker, meeting_id="m2")
    await _publish(client, m2)
    kind, org, mid, _ = queue.calls[-1]
    assert (kind, org, mid) == ("notify", "org_a", m2)


async def test_notify_job_posts_summary(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession], discord: Recorder
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    await _configure(client)
    await _publish(client, mid)
    rec = Recorder()
    await notify_published(
        sessionmaker,
        DiscordClient(httpx.MockTransport(rec)),
        org_id="org_a",
        meeting_id=mid,
        app_url="https://meetmind.test",
    )
    url, body = rec.sent[0]
    assert url == HOOK
    embed = body["embeds"][0]  # type: ignore[index]
    assert embed["url"] == f"https://meetmind.test/meetings/{mid}/minutes"
    assert "Quyết định" in json.dumps(embed, ensure_ascii=False)


async def test_notify_job_skips_other_org_and_swallows_errors(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession], discord: Recorder
) -> None:
    mid = await seed_analyzed_meeting(sessionmaker)
    await _configure(client)
    await _publish(client, mid)
    rec = Recorder(status=500)
    failing = DiscordClient(httpx.MockTransport(rec))
    await notify_published(sessionmaker, failing, org_id="org_a", meeting_id=mid, app_url="x")
    assert len(rec.sent) == 1  # attempted once, error logged, nothing raised
    await _configure(client, org="org_b")
    await notify_published(sessionmaker, failing, org_id="org_b", meeting_id=mid, app_url="x")
    assert len(rec.sent) == 1  # org_b cannot see org_a's meeting


async def test_digest_requires_secret(client: httpx.AsyncClient, discord: Recorder) -> None:
    assert (await client.post("/internal/digest")).status_code == 401
    r = await client.post("/internal/digest", headers={"X-Cron-Secret": "wrong"})
    assert r.status_code == 401


async def test_digest_disabled_without_secret(client: httpx.AsyncClient) -> None:
    r = await client.post("/internal/digest", headers={"X-Cron-Secret": ""})
    assert r.status_code == 503 and r.json()["error"]["code"] == "digest_disabled"


async def _set_due(sm: async_sessionmaker[AsyncSession], org: str, mid: str, due: date) -> str:
    async with sm() as s:
        rows = await items_repo.list_for_meeting(s, org_id=org, meeting_id=mid)
        row = next(r for r in rows if r.type == ItemType.ACTION_ITEM.value)
        model = items_repo.to_model(row).model_copy(update={"due_date": due})
        await items_repo.save(s, item=row, model=model)
        await s.commit()
        return model.content


async def test_digest_sends_due_tasks_per_org(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession], discord: Recorder
) -> None:
    await _configure(client, org="org_a")
    await _configure(client, org="org_b", digest=False)  # digest off: skipped
    a = await seed_analyzed_meeting(sessionmaker, org_id="org_a", meeting_id="ma")
    b = await seed_analyzed_meeting(sessionmaker, org_id="org_b", meeting_id="mb")
    await _publish(client, a, org="org_a")
    await _publish(client, b, org="org_b")
    content = await _set_due(sessionmaker, "org_a", a, date(2026, 10, 14))
    await _set_due(sessionmaker, "org_b", b, date(2026, 10, 14))
    discord.sent.clear()

    h = {"X-Cron-Secret": SECRET}
    r = await client.post("/internal/digest", params={"on": "2026-10-14"}, headers=h)
    assert r.status_code == 200 and r.json() == {"orgs": 1, "sent": 1, "failed": 0}
    url, body = discord.sent[0]
    embed = body["embeds"][0]  # type: ignore[index]
    assert url == HOOK and embed["title"] == "Nhắc việc ngày 14/10/2026"
    assert embed["url"] == "https://meetmind.test"
    assert content.split()[0] in json.dumps(embed, ensure_ascii=False)

    r = await client.post("/internal/digest", params={"on": "2026-11-30"}, headers=h)
    assert r.json() == {"orgs": 1, "sent": 0, "failed": 0}


async def test_invite_link_saved_kept_cleared_and_visible_to_members(
    client: httpx.AsyncClient, discord: Recorder
) -> None:
    invite = "https://discord.gg/meetmind"
    r = await client.put(
        "/settings/discord", json={"invite_url": invite, "digest_enabled": False}, headers=auth()
    )
    assert r.json()["invite_url"] == invite and r.json()["configured"] is False
    member = auth(user="m1", role="member")
    assert (await client.get("/settings/discord", headers=member)).json()["invite_url"] == invite
    r = await client.put("/settings/discord", json={"digest_enabled": True}, headers=auth())
    assert r.json()["invite_url"] == invite  # omitted: kept
    r = await client.put(
        "/settings/discord", json={"invite_url": "", "digest_enabled": True}, headers=auth()
    )
    assert r.json()["invite_url"] is None
    other_org = await client.get("/settings/discord", headers=auth(org="org_b"))
    assert other_org.json()["invite_url"] is None


async def test_invalid_invite_link_rejected(client: httpx.AsyncClient, discord: Recorder) -> None:
    r = await client.put(
        "/settings/discord",
        json={"invite_url": "https://evil.io/x", "digest_enabled": False},
        headers=auth(),
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_invite"
