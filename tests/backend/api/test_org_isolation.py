from dataclasses import dataclass

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.api_helpers import auth
from tests.backend.pipeline_helpers import seed_analyzed_meeting

from app.models import Job
from app.repositories import items as items_repo
from app.repositories import meetings

pytestmark = pytest.mark.db

MID = "mb"


@dataclass
class OrgB:
    meeting_id: str
    item_id: str
    job_id: str


@pytest.fixture
async def org_b(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> OrgB:
    await seed_analyzed_meeting(sessionmaker, org_id="org_b", meeting_id=MID)
    hb = auth(org="org_b")
    listed = (await client.get(f"/meetings/{MID}/items", headers=hb)).json()
    for it in listed:
        r = await client.patch(f"/items/{it['id']}", json={"action": "approve"}, headers=hb)
        assert r.status_code == 200
    pub = await client.post(f"/meetings/{MID}/publish", headers=hb)
    assert pub.status_code == 200 and pub.json()["status"] == "published"
    async with sessionmaker() as s:
        job_id = await s.scalar(select(Job.id).where(Job.org_id == "org_b", Job.meeting_id == MID))
    assert job_id is not None
    return OrgB(MID, listed[0]["id"], job_id)


async def _snapshot(sm: async_sessionmaker[AsyncSession], b: OrgB) -> tuple[str, int, str]:
    async with sm() as s:
        item = await items_repo.get(s, org_id="org_b", item_id=b.item_id)
        assert item is not None
        events = await items_repo.events(s, org_id="org_b", item_id=b.item_id)
        meeting = await meetings.get(s, org_id="org_b", meeting_id=b.meeting_id)
        assert meeting is not None
        return item.review_state, len(events), meeting.status


CASES: list[tuple[str, str, dict[str, object] | None]] = [
    ("GET", "/meetings/{m}", None),
    ("POST", "/meetings/{m}/reanalyze", None),
    ("DELETE", "/meetings/{m}", None),
    ("GET", "/meetings/{m}/items", None),
    ("GET", "/meetings/{m}/topics", None),
    ("POST", "/meetings/{m}/items/approve-clean", None),
    ("POST", "/meetings/{m}/publish", None),
    ("GET", "/meetings/{m}/export?format=md", None),
    ("GET", "/meetings/{m}/speakers", None),
    ("POST", "/meetings/{m}/speakers", {"speakers": [{"label": "Người nói A", "name": "Lan"}]}),
    ("GET", "/jobs/{j}", None),
    ("PATCH", "/items/{i}", {"action": "approve"}),
    ("GET", "/items/{i}/events", None),
    ("POST", "/items/{i}/report", {"reason": "wrong"}),
    ("POST", "/items/{i}/reopen", {}),
]


@pytest.mark.parametrize(("method", "path", "body"), CASES, ids=[f"{m} {p}" for m, p, _ in CASES])
async def test_cross_org_access_is_404(
    client: httpx.AsyncClient,
    sessionmaker: async_sessionmaker[AsyncSession],
    org_b: OrgB,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    before = await _snapshot(sessionmaker, org_b)
    url = path.format(m=org_b.meeting_id, j=org_b.job_id, i=org_b.item_id)
    r = await client.request(method, url, json=body, headers=auth(org="org_a"))
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "not_found"
    assert await _snapshot(sessionmaker, org_b) == before


# The seeded meeting is published, so /speakers answers 409 for its owner; the owner's 200 for
# that endpoint is covered by test_audio_flow.
GET_CASES = [c for c in CASES if c[0] == "GET" and "/speakers" not in c[1]]


@pytest.mark.parametrize(
    ("method", "path", "body"), GET_CASES, ids=[f"{m} {p}" for m, p, _ in GET_CASES]
)
async def test_owner_org_is_not_404(
    client: httpx.AsyncClient,
    org_b: OrgB,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    """Positive control: the same request from the owning org succeeds, so the 404s above
    are caused by the org mismatch and not by a wrong URL."""
    url = path.format(m=org_b.meeting_id, j=org_b.job_id, i=org_b.item_id)
    r = await client.request(method, url, json=body, headers=auth(org="org_b"))
    assert r.status_code == 200, r.text


async def test_org_a_list_is_empty_and_org_b_untouched(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession], org_b: OrgB
) -> None:
    before = await _snapshot(sessionmaker, org_b)
    r = await client.get("/meetings", headers=auth(org="org_a"))
    assert r.status_code == 200 and r.json() == []
    assert before[2] == "published"
    assert len((await client.get("/meetings", headers=auth(org="org_b"))).json()) == 1


async def test_discord_settings_are_per_org(client: httpx.AsyncClient) -> None:
    """Settings have no id in the URL: org isolation means org_a never sees org_b's webhook."""
    hook = "https://discord.com/api/webhooks/1/org-b-token"
    r = await client.put(
        "/settings/discord",
        json={"webhook_url": hook, "digest_enabled": True},
        headers=auth(org="org_b"),
    )
    assert r.status_code == 200 and r.json()["configured"] is True
    mine = await client.get("/settings/discord", headers=auth(org="org_a"))
    assert mine.json() == {
        "configured": False, "webhook_hint": None, "digest_enabled": False, "invite_url": None
    }
    test = await client.post("/settings/discord/test", headers=auth(org="org_a"))
    assert test.status_code == 409 and test.json()["error"]["code"] == "not_configured"
