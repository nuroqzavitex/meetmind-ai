import json
from datetime import date
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI
from tests.backend.api_helpers import auth

from app.core.errors import ServiceUnavailable
from app.notify.discord import DiscordClient
from app.notify.discord_bot import ADMINISTRATOR, MANAGE_GUILD
from app.schemas.qa import Citation, QAResponse
from app.services import discord_bot

pytestmark = pytest.mark.db

KEY = Ed25519PrivateKey.generate()
PUBLIC_HEX = KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
GUILD = "900000000000000001"


class Recorder:
    def __init__(self) -> None:
        self.patches: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.patches.append((str(request.url), json.loads(request.content)))
        return httpx.Response(200, json={})


@pytest.fixture
def bot(app: FastAPI) -> Recorder:
    rec = Recorder()
    app.state.discord = DiscordClient(httpx.MockTransport(rec))
    app.state.settings.discord_app_id = "app123"
    app.state.settings.discord_public_key = PUBLIC_HEX
    app.state.settings.frontend_url = "https://meetmind.test"
    return rec


async def _send(
    client: httpx.AsyncClient, payload: dict[str, Any], *, key: Ed25519PrivateKey = KEY
) -> httpx.Response:
    body = json.dumps(payload).encode()
    ts = "1760400000"
    sig = key.sign(ts.encode() + body).hex()
    return await client.post(
        "/discord/interactions",
        content=body,
        headers={"X-Signature-Ed25519": sig, "X-Signature-Timestamp": ts,
                 "Content-Type": "application/json"},
    )


def _command(name: str, value: str, *, perms: int = 0, guild: str | None = GUILD) -> dict[str, Any]:
    opt = "ma" if name == "ketnoi" else "cau_hoi"
    payload: dict[str, Any] = {
        "type": 2, "application_id": "app123", "token": "tok-1",
        "data": {"name": name, "options": [{"name": opt, "type": 3, "value": value}]},
        "member": {"permissions": str(perms), "user": {"id": "42", "username": "minh"}},
    }
    if guild:
        payload["guild_id"] = guild
    return payload


async def _link_code(client: httpx.AsyncClient, org: str = "org_a") -> str:
    r = await client.get("/settings/discord-bot", headers=auth(org=org, user=f"admin_{org}"))
    assert r.status_code == 200, r.text
    return str(r.json()["link_code"])


async def test_ping_and_signature(client: httpx.AsyncClient, bot: Recorder) -> None:
    assert (await _send(client, {"type": 1})).json() == {"type": 1}
    bad = await _send(client, {"type": 1}, key=Ed25519PrivateKey.generate())
    assert bad.status_code == 401
    unsigned = await client.post("/discord/interactions", json={"type": 1})
    assert unsigned.status_code == 401


async def test_disabled_without_public_key(client: httpx.AsyncClient, app: FastAPI) -> None:
    app.state.settings.discord_public_key = ""
    r = await client.post("/discord/interactions", json={"type": 1})
    assert r.status_code == 503


async def test_bot_settings_are_admin_only(client: httpx.AsyncClient, bot: Recorder) -> None:
    member = auth(user="m1", role="member")
    for method, path in [
        ("GET", "/settings/discord-bot"),
        ("POST", "/settings/discord-bot/rotate-code"),
        ("POST", "/settings/discord-bot/unlink"),
    ]:
        r = await client.request(method, path, headers=member)
        assert r.status_code == 403, path
    got = (await client.get("/settings/discord-bot", headers=auth())).json()
    assert got["available"] is True and got["linked"] is False
    assert got["link_code"].startswith("DC-")
    assert got["install_url"] == (
        "https://discord.com/oauth2/authorize?client_id=app123&scope=applications.commands"
    )


async def test_link_requires_manage_server_and_a_valid_code(
    client: httpx.AsyncClient, bot: Recorder
) -> None:
    code = await _link_code(client)
    no_perm = (await _send(client, _command("ketnoi", code))).json()
    assert no_perm["data"]["flags"] == 64 and "quản lý server" in no_perm["data"]["content"]
    wrong = (await _send(client, _command("ketnoi", "DC-AAAA-BBBB", perms=MANAGE_GUILD))).json()
    assert "không đúng" in wrong["data"]["content"]
    ok = (await _send(client, _command("ketnoi", code.lower(), perms=ADMINISTRATOR))).json()
    assert "Đã liên kết" in ok["data"]["content"]
    assert (await client.get("/settings/discord-bot", headers=auth())).json()["linked"] is True


async def test_ask_unlinked_server_and_dm(client: httpx.AsyncClient, bot: Recorder) -> None:
    r = (await _send(client, _command("hoi", "Chốt gì?"))).json()
    assert r["type"] == 4 and "chưa liên kết" in r["data"]["content"]
    dm = (await _send(client, _command("hoi", "Chốt gì?", guild=None))).json()
    assert "server Discord" in dm["data"]["content"]


async def test_ask_answers_with_citations(
    client: httpx.AsyncClient, bot: Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    async def fake_ask(*_: Any, principal: Any, question: str, **__: Any) -> QAResponse:
        seen.update(org=principal.org_id, question=question)
        return QAResponse(
            answer="Nhóm chốt dùng PostgreSQL [1].",
            citations=[Citation(
                ref=1, meeting_id="m1", title="Họp thanh toán", date=date(2026, 10, 8),
                ts="00:03:30", speaker="Lan", quote="Vậy mình chốt Postgres nhé.", utterance_id="u8",
            )],
        )

    monkeypatch.setattr(discord_bot.qa, "ask", fake_ask)
    await _send(client, _command("ketnoi", await _link_code(client), perms=MANAGE_GUILD))
    r = await _send(client, _command("hoi", "Dùng CSDL nào?"))
    assert r.json() == {"type": 5}  # deferred: "đang suy nghĩ…"
    assert seen == {"org": "org_a", "question": "Dùng CSDL nào?"}
    url, body = bot.patches[-1]
    assert url == "https://discord.com/api/v10/webhooks/app123/tok-1/messages/@original"
    embed = body["embeds"][0]
    assert embed["description"] == "Nhóm chốt dùng PostgreSQL [1]."
    sources = embed["fields"][0]["value"]
    assert "[Họp thanh toán](https://meetmind.test/meetings/m1/minutes)" in sources
    assert "08/10/2026 · 00:03:30 · Lan" in sources
    assert body["allowed_mentions"] == {"parse": []}


async def test_ask_reports_ai_errors(
    client: httpx.AsyncClient, bot: Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing(*_: Any, **__: Any) -> QAResponse:
        raise ServiceUnavailable("Dịch vụ AI chưa sẵn sàng, vui lòng thử lại sau", "llm_unavailable")

    monkeypatch.setattr(discord_bot.qa, "ask", failing)
    await _send(client, _command("ketnoi", await _link_code(client), perms=MANAGE_GUILD))
    await _send(client, _command("hoi", "Dùng CSDL nào?"))
    assert bot.patches[-1][1]["content"] == "⚠️ Dịch vụ AI chưa sẵn sàng, vui lòng thử lại sau"


async def test_server_answers_only_for_its_org(
    client: httpx.AsyncClient, bot: Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    orgs: list[str] = []

    async def fake_ask(*_: Any, principal: Any, **__: Any) -> QAResponse:
        orgs.append(principal.org_id)
        return QAResponse(answer="x", citations=[])

    monkeypatch.setattr(discord_bot.qa, "ask", fake_ask)
    await _send(client, _command("ketnoi", await _link_code(client, "org_a"), perms=MANAGE_GUILD))
    # Re-linking the same server from org_b moves it: one server answers for one org.
    await _send(client, _command("ketnoi", await _link_code(client, "org_b"), perms=MANAGE_GUILD))
    await _send(client, _command("hoi", "q"))
    assert orgs == ["org_b"]
    a = (await client.get("/settings/discord-bot", headers=auth(org="org_a", user="admin_org_a"))).json()
    assert a["linked"] is False
    r = await client.post("/settings/discord-bot/unlink", headers=auth(org="org_b", user="admin_org_b"))
    assert r.json()["linked"] is False
    assert "chưa liên kết" in (await _send(client, _command("hoi", "q"))).json()["data"]["content"]


async def test_rotating_the_code_invalidates_the_old_one(
    client: httpx.AsyncClient, bot: Recorder
) -> None:
    old = await _link_code(client)
    new = (await client.post("/settings/discord-bot/rotate-code", headers=auth())).json()["link_code"]
    assert new != old
    r = (await _send(client, _command("ketnoi", old, perms=MANAGE_GUILD))).json()
    assert "không đúng" in r["data"]["content"]


def _overview(name: str, **opts: str) -> dict[str, Any]:
    payload = _command(name, "")
    payload["data"]["options"] = [{"name": k, "type": 3, "value": v} for k, v in opts.items()]
    return payload


async def test_overview_commands_answer_from_published_minutes(
    client: httpx.AsyncClient, bot: Recorder, sessionmaker: Any
) -> None:
    from tests.backend.pipeline_helpers import seed_analyzed_meeting

    await seed_analyzed_meeting(sessionmaker)
    for it in (await client.get("/meetings/m1/items", headers=auth())).json():
        await client.patch(f"/items/{it['id']}", json={"action": "approve"}, headers=auth())
    await client.post("/meetings/m1/publish", headers=auth())
    code = await _link_code(client)
    await _send(client, _command("ketnoi", code, perms=MANAGE_GUILD))

    r = (await _send(client, _overview("quyetdinh"))).json()
    assert r["type"] == 4 and "flags" not in r["data"]  # public, answered at once
    assert r["data"]["content"].startswith("🧭 **Quyết định gần đây**")
    assert "Postgre" in r["data"]["content"]

    r = (await _send(client, _overview("viec", ten="minh"))).json()
    assert r["data"]["content"].startswith("🗂️ **Việc của Minh**")

    r = (await _send(client, _overview("chuongtrinh"))).json()
    assert r["data"]["content"].startswith("**📋 Chương trình họp kế tiếp**")
    assert r["data"]["allowed_mentions"] == {"parse": []}
    assert bot.patches == []  # no background follow-up for these commands


async def test_tasks_command_needs_a_name_and_a_linked_server(
    client: httpx.AsyncClient, bot: Recorder
) -> None:
    r = (await _send(client, _overview("viec", ten="Minh"))).json()
    assert "chưa liên kết" in r["data"]["content"]
    code = await _link_code(client)
    await _send(client, _command("ketnoi", code, perms=MANAGE_GUILD))
    r = (await _send(client, _overview("viec"))).json()
    assert r["data"]["flags"] == 64 and "/viec ten:" in r["data"]["content"]
