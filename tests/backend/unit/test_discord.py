import json
from datetime import date

import httpx
import pytest

from app.ai.domain.enums import ItemStatus, ItemType, ReviewState
from app.ai.domain.models import Evidence, MeetingContext, MeetingItem
from app.notify.discord import DiscordClient, DiscordError, is_webhook_url, webhook_hint
from app.notify.messages import (
    MAX_FIELD,
    DueTask,
    digest_message,
    published_message,
    select_digest,
)

TODAY = date(2026, 10, 14)
CTX = MeetingContext(
    meeting_id="m1", title="Họp dự án", meeting_date=date(2026, 10, 9), project="CRM"
)
HOOK = "https://discord.com/api/webhooks/123456/abc-DEF_xyz"


def _item(n: int, type_: ItemType, content: str, **kw: object) -> MeetingItem:
    fields: dict[str, object] = {
        "id": f"m1-i{n:03d}",
        "meeting_id": "m1",
        "type": type_,
        "content": content,
        "evidence": [Evidence(utterance_id="u1", speaker="Lan", ts="00:03:30", quote="q")],
        "review_state": ReviewState.APPROVED,
    }
    fields.update(kw)
    return MeetingItem.model_validate(fields)


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        (HOOK, True),
        ("https://discordapp.com/api/webhooks/1/tok", True),
        ("http://discord.com/api/webhooks/1/tok", False),
        ("https://discord.com.evil.io/api/webhooks/1/tok", False),
        ("https://evil.io/?u=https://discord.com/api/webhooks/1/tok", False),
        ("https://discord.com/api/webhooks/1/tok/../../x", False),
        ("https://discord.com/api/webhooks/abc/tok", False),
        ("", False),
    ],
)
def test_is_webhook_url(url: str, ok: bool) -> None:
    assert is_webhook_url(url) is ok


def test_webhook_hint_only_shows_the_tail() -> None:
    assert webhook_hint(HOOK) == "…_xyz"


def test_published_message_lists_kept_decisions_and_tasks() -> None:
    items = [
        _item(1, ItemType.DECISION, "Dùng PostgreSQL"),
        _item(2, ItemType.ACTION_ITEM, "Viết migration", owner="Minh", due_date=date(2026, 10, 16)),
        _item(3, ItemType.DECISION, "MongoDB", status=ItemStatus.SUPERSEDED),
        _item(4, ItemType.ACTION_ITEM, "REJECTED", review_state=ReviewState.REJECTED),
        _item(5, ItemType.OPEN_QUESTION, "Ai duyệt ngân sách?"),
    ]
    msg = published_message(CTX, items, "https://app/meetings/m1/minutes")
    embed = msg["embeds"][0]
    assert embed["title"] == "Họp dự án" and embed["url"] == "https://app/meetings/m1/minutes"
    assert "09/10/2026" in embed["description"] and "CRM" in embed["description"]
    text = json.dumps(msg, ensure_ascii=False)
    assert "Dùng PostgreSQL" in text
    assert "**Minh** – Viết migration (hạn 16/10/2026)" in text
    assert "MongoDB" not in text and "REJECTED" not in text
    assert "1 câu hỏi" in text


def test_published_message_without_items_still_has_a_field() -> None:
    msg = published_message(CTX, [], "u")
    assert msg["embeds"][0]["fields"][0]["name"] == "Nội dung"


def test_long_lists_are_truncated_within_discord_limits() -> None:
    items = [_item(i, ItemType.DECISION, "x" * 300) for i in range(30)]
    field = published_message(CTX, items, "u")["embeds"][0]["fields"][0]
    assert len(field["value"]) <= MAX_FIELD
    assert field["value"].endswith("mục khác")


def _due(n: int, due: date | None, **kw: object) -> DueTask:
    return DueTask(_item(n, ItemType.ACTION_ITEM, f"task{n}", due_date=due, **kw), "m1", "Họp")


def test_select_digest_buckets_by_due_date() -> None:
    tasks = [
        _due(1, date(2026, 10, 6)),   # 8 days late: dropped
        _due(2, date(2026, 10, 7)),   # 7 days late: overdue
        _due(3, date(2026, 10, 13)),  # overdue
        _due(4, TODAY),
        _due(5, date(2026, 10, 16)),  # +2: upcoming
        _due(6, date(2026, 10, 17)),  # +3: dropped
        _due(7, None),
        _due(8, TODAY, review_state=ReviewState.REJECTED),
        _due(9, TODAY, status=ItemStatus.SUPERSEDED),
    ]
    d = select_digest(tasks, TODAY)
    assert [t.item.content for t in d.overdue] == ["task2", "task3"]
    assert [t.item.content for t in d.today] == ["task4"]
    assert [t.item.content for t in d.upcoming] == ["task5"]


def test_select_digest_empty() -> None:
    assert select_digest([_due(1, date(2026, 11, 1))], TODAY).empty()


def test_digest_message_sections() -> None:
    d = select_digest([_due(1, date(2026, 10, 13), owner="Lan"), _due(2, TODAY)], TODAY)
    embed = digest_message(d, TODAY, "https://app")["embeds"][0]
    assert embed["title"] == "Nhắc việc ngày 14/10/2026"
    names = [f["name"] for f in embed["fields"]]
    assert names == ["⚠️ Quá hạn (1)", "📌 Đến hạn hôm nay (1)"]
    assert "**Lan** – task1 (hạn 13/10/2026)" in embed["fields"][0]["value"]
    assert "(hạn" not in embed["fields"][1]["value"]


async def test_client_posts_json_without_mentions() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    await DiscordClient(httpx.MockTransport(handler)).send(HOOK, {"content": "@everyone hi"})
    body = json.loads(seen[0].content)
    assert str(seen[0].url) == HOOK
    assert body["allowed_mentions"] == {"parse": []}


@pytest.mark.parametrize(
    ("status", "match"), [(404, "không còn tồn tại"), (429, "HTTP 429"), (500, "HTTP 500")]
)
async def test_client_errors(status: int, match: str) -> None:
    client = DiscordClient(httpx.MockTransport(lambda _: httpx.Response(status)))
    with pytest.raises(DiscordError, match=match):
        await client.send(HOOK, {})


async def test_client_network_error() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    with pytest.raises(DiscordError, match="Không kết nối"):
        await DiscordClient(httpx.MockTransport(boom)).send(HOOK, {})
