import json

import httpx
import pytest
from fastapi import FastAPI
from tests.backend.api_helpers import auth

from app.core.clerk_api import ClerkAPI
from app.notify.discord import DiscordClient

pytestmark = pytest.mark.db

HOOK = "https://discord.com/api/webhooks/1/tok"
ADMIN = {"org": "org_a", "user": "admin_1", "name": "Lan"}


class FakeClerk:
    """Answers the three Clerk Backend API calls the app makes."""

    def __init__(self) -> None:
        self.added: list[tuple[str, str]] = []
        self.fail_add = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/v1")
        if request.method == "GET" and path.startswith("/users/"):
            uid = path.split("/")[-1]
            return httpx.Response(200, json={
                "first_name": "Minh", "last_name": uid, "primary_email_address_id": "e1",
                "email_addresses": [{"id": "e1", "email_address": f"{uid}@example.com"}],
            })
        if request.method == "GET" and path.startswith("/organizations/"):
            return httpx.Response(200, json={"name": f"Org {path.split('/')[-1]}"})
        if request.method == "POST" and path.endswith("/memberships"):
            if self.fail_add:
                return httpx.Response(500, json={})
            org = path.split("/")[2]
            self.added.append((org, json.loads(request.content)["user_id"]))
            return httpx.Response(200, json={})
        return httpx.Response(404)


@pytest.fixture
def clerk(app: FastAPI) -> FakeClerk:
    fake = FakeClerk()
    app.state.clerk = ClerkAPI("sk_test", transport=httpx.MockTransport(fake))
    return fake


async def _code(client: httpx.AsyncClient, org: str = "org_a") -> str:
    r = await client.get("/settings/join-code", headers=auth(org=org, user=f"admin_{org}"))
    assert r.status_code == 200, r.text
    return str(r.json()["code"])


async def _request(client: httpx.AsyncClient, code: str, user: str = "u_new") -> httpx.Response:
    return await client.post("/join-requests", json={"code": code}, headers=auth(org=None, user=user))


async def test_join_code_is_stable_and_rotates(client: httpx.AsyncClient, clerk: FakeClerk) -> None:
    code = await _code(client)
    assert code.startswith("MM-") and len(code) == 12
    assert await _code(client) == code
    r = await client.post("/settings/join-code/rotate", headers=auth(**ADMIN))
    new = r.json()["code"]
    assert new != code
    assert (await _request(client, code)).json()["error"]["code"] == "invalid_code"
    assert (await _request(client, new)).status_code == 201


async def test_members_cannot_see_code_or_requests(client: httpx.AsyncClient, clerk: FakeClerk) -> None:
    member = auth(org="org_a", user="m1", role="member")
    for method, path in [
        ("GET", "/settings/join-code"),
        ("POST", "/settings/join-code/rotate"),
        ("GET", "/join-requests"),
    ]:
        r = await client.request(method, path, headers=member)
        assert r.status_code == 403 and r.json()["error"]["code"] == "admin_only", path


async def test_request_then_approve_adds_member(client: httpx.AsyncClient, clerk: FakeClerk) -> None:
    code = await _code(client)
    r = await _request(client, code.lower().replace("-", " "))  # typed loosely
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["status"] == "pending" and req["org_name"] == "Org org_a"
    assert req["user_name"] == "Minh u_new" and req["user_email"] == "u_new@example.com"

    mine = (await client.get("/join-requests/mine", headers=auth(org=None, user="u_new"))).json()
    assert [m["id"] for m in mine] == [req["id"]]

    pending = (await client.get("/join-requests", headers=auth(**ADMIN))).json()
    assert [p["id"] for p in pending] == [req["id"]]

    r = await client.post(f"/join-requests/{req['id']}/approve", headers=auth(**ADMIN))
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert clerk.added == [("org_a", "u_new")]
    assert (await client.get("/join-requests", headers=auth(**ADMIN))).json() == []
    again = await client.post(f"/join-requests/{req['id']}/reject", headers=auth(**ADMIN))
    assert again.status_code == 409 and again.json()["error"]["code"] == "not_pending"


async def test_reject_does_not_call_clerk(client: httpx.AsyncClient, clerk: FakeClerk) -> None:
    req = (await _request(client, await _code(client))).json()
    r = await client.post(f"/join-requests/{req['id']}/reject", headers=auth(**ADMIN))
    assert r.json()["status"] == "rejected" and clerk.added == []


async def test_clerk_failure_keeps_request_pending(client: httpx.AsyncClient, clerk: FakeClerk) -> None:
    req = (await _request(client, await _code(client))).json()
    clerk.fail_add = True
    r = await client.post(f"/join-requests/{req['id']}/approve", headers=auth(**ADMIN))
    assert r.status_code == 502 and r.json()["error"]["code"] == "clerk_error"
    assert len((await client.get("/join-requests", headers=auth(**ADMIN))).json()) == 1


async def test_without_secret_key_is_503(client: httpx.AsyncClient, app: FastAPI) -> None:
    app.state.clerk = ClerkAPI(None)
    code = await _code(client)
    r = await _request(client, code)
    assert r.status_code == 503 and r.json()["error"]["code"] == "clerk_unavailable"


async def test_duplicates_limits_and_cancel(client: httpx.AsyncClient, clerk: FakeClerk) -> None:
    code = await _code(client)
    first = (await _request(client, code)).json()
    dup = await _request(client, code)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "already_requested"

    other = auth(org=None, user="someone_else")
    r = await client.delete(f"/join-requests/{first['id']}", headers=other)
    assert r.status_code == 404
    r = await client.delete(f"/join-requests/{first['id']}", headers=auth(org=None, user="u_new"))
    assert r.status_code == 204
    assert (await _request(client, code)).status_code == 201  # may ask again after cancelling

    for i in range(4):
        assert (await _request(client, await _code(client, f"org_{i}"))).status_code == 201
    too_many = await _request(client, await _code(client, "org_x"))
    assert too_many.status_code == 429 and too_many.json()["error"]["code"] == "too_many_requests"


async def test_member_of_org_cannot_request_it(client: httpx.AsyncClient, clerk: FakeClerk) -> None:
    code = await _code(client)
    r = await client.post("/join-requests", json={"code": code}, headers=auth(org="org_a", user="x"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_member"


async def test_bad_codes(client: httpx.AsyncClient, clerk: FakeClerk) -> None:
    for code in ["", "abc", "MM-0000-0000", "MM-ZZZZ-ZZZZ"]:
        r = await _request(client, code)
        assert r.status_code in (404, 422), code


async def test_admin_of_other_org_cannot_decide(client: httpx.AsyncClient, clerk: FakeClerk) -> None:
    req = (await _request(client, await _code(client, "org_a"))).json()
    other_admin = auth(org="org_b", user="admin_b")
    for action in ("approve", "reject"):
        r = await client.post(f"/join-requests/{req['id']}/{action}", headers=other_admin)
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    assert (await client.get("/join-requests", headers=other_admin)).json() == []
    assert clerk.added == []


async def test_new_request_posts_to_discord(
    client: httpx.AsyncClient, clerk: FakeClerk, app: FastAPI
) -> None:
    sent: list[dict[str, object]] = []

    def hook(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(204)

    app.state.discord = DiscordClient(httpx.MockTransport(hook))
    r = await client.put(
        "/settings/discord", json={"webhook_url": HOOK, "digest_enabled": False}, headers=auth(**ADMIN)
    )
    assert r.status_code == 200
    assert (await _request(client, await _code(client))).status_code == 201
    text = json.dumps(sent, ensure_ascii=False)
    assert "Minh u_new" in text and "u_new@example.com" in text and "/settings" in text


async def test_approved_request_carries_the_discord_invite(
    client: httpx.AsyncClient, clerk: FakeClerk
) -> None:
    await client.put(
        "/settings/discord",
        json={"invite_url": "https://discord.gg/team-a", "digest_enabled": False},
        headers=auth(**ADMIN),
    )
    req = (await _request(client, await _code(client))).json()
    assert req["discord_invite_url"] is None  # not shown before approval
    mine = auth(org=None, user="u_new")
    assert (await client.get("/join-requests/mine", headers=mine)).json()[0]["discord_invite_url"] is None
    await client.post(f"/join-requests/{req['id']}/approve", headers=auth(**ADMIN))
    got = (await client.get("/join-requests/mine", headers=mine)).json()[0]
    assert got["status"] == "approved" and got["discord_invite_url"] == "https://discord.gg/team-a"
