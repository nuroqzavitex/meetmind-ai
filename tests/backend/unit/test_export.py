from datetime import date

from app.ai.domain.enums import ItemStatus, ItemType, ReviewState
from app.ai.domain.models import Evidence, MeetingContext, MeetingItem
from app.services.export import render_json, render_markdown

CTX = MeetingContext(meeting_id="m1", title="Họp dự án", meeting_date=date(2026, 10, 9))


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


def _items() -> list[MeetingItem]:
    return [
        _item(1, ItemType.DECISION, "Dùng PostgreSQL", supersedes=["MongoDB"]),
        _item(
            2,
            ItemType.ACTION_ITEM,
            "Viết migration",
            owner="Minh",
            due_date=date(2026, 10, 16),
            review_state=ReviewState.EDITED,
        ),
        _item(3, ItemType.BLOCKER, "PENDING-ITEM", review_state=ReviewState.PENDING),
        _item(4, ItemType.REQUEST, "REJECTED-ITEM", review_state=ReviewState.REJECTED),
        _item(5, ItemType.DECISION, "SUPERSEDED-ITEM", status=ItemStatus.SUPERSEDED),
    ]


def test_markdown_layout() -> None:
    md = render_markdown(CTX, _items(), None)
    assert md.startswith("# Họp dự án\n")
    assert "Ngày: 09/10/2026 · Dự án: —" in md
    assert "## Quyết định" in md and "## Việc cần làm" in md
    assert "(thay cho: MongoDB)" in md
    assert "(hạn 16/10/2026)" in md
    assert "[00:03:30 Lan]" in md
    assert "— Minh" in md
    for hidden in ("PENDING-ITEM", "REJECTED-ITEM", "SUPERSEDED-ITEM"):
        assert hidden not in md
    assert "## Vướng mắc" not in md and "## Yêu cầu" not in md


def test_markdown_footer() -> None:
    from datetime import UTC, datetime

    md = render_markdown(CTX, _items(), datetime(2026, 10, 10, tzinfo=UTC))
    assert "Phát hành: 10/10/2026" in md


def test_json_items() -> None:
    out = render_json(CTX, _items())
    assert len(out["items"]) == 2
    assert out["meeting"]["title"] == "Họp dự án"


def test_markdown_bullet_collapses_newlines() -> None:
    item = _item(1, ItemType.DECISION, "Dòng một\n## Chèn heading\n\n- bullet giả", owner="A\nB")
    md = render_markdown(CTX, [item], None)
    assert "- Dòng một ## Chèn heading - bullet giả — A B" in md
    assert "\n## Chèn" not in md
