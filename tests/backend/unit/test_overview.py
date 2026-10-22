from datetime import date

from app.ai.domain.enums import ItemStatus, ItemType
from app.ai.domain.models import Hold
from app.schemas.overview import OverviewEntry
from app.services.overview import (
    DISCORD_LIMIT,
    build_agenda,
    build_decisions,
    build_tasks,
    clip,
    decisions_message,
    due_state,
    tasks_message,
)

TODAY = date(2026, 10, 22)


def _e(n: int, type_: ItemType, content: str, *, meeting_date: date = date(2026, 10, 19),
       **kw: object) -> OverviewEntry:
    fields: dict[str, object] = {
        "item_id": f"i{n}", "meeting_id": f"m{n}", "meeting_title": f"Họp {n}",
        "meeting_date": meeting_date, "project": "Thông báo", "type": type_,
        "status": ItemStatus.OPEN if type_ == ItemType.OPEN_QUESTION else ItemStatus.FINAL,
        "content": content,
    }
    fields.update(kw)
    if type_ == ItemType.ACTION_ITEM:
        fields["due_state"] = due_state(fields.get("due_date"), TODAY)  # type: ignore[arg-type]
    return OverviewEntry.model_validate(fields)


def test_due_state() -> None:
    assert due_state(None, TODAY) is None
    assert due_state(date(2026, 10, 21), TODAY) == "overdue"
    assert due_state(TODAY, TODAY) == "today"
    assert due_state(date(2026, 10, 29), TODAY) == "soon"
    assert due_state(date(2026, 10, 30), TODAY) == "later"


def test_agenda_collects_what_is_still_open() -> None:
    declined = Hold(reason="declined", quote="Tuần này em kín lịch rồi.", phrase="kín lịch",
                    speaker="Quốc", ts="00:03:05")
    entries = [
        _e(1, ItemType.OPEN_QUESTION, "Ai làm dashboard?", hold=declined),
        _e(2, ItemType.OPEN_QUESTION, "Dùng lại icon cũ?", meeting_date=date(2026, 10, 12)),
        _e(3, ItemType.ACTION_ITEM, "Soạn mẫu tiếng Anh", owner="Vân", condition="pháp chế duyệt"),
        _e(4, ItemType.ACTION_ITEM, "Dựng hàng đợi", owner="Quốc", due_date=TODAY),
        _e(5, ItemType.ACTION_ITEM, "Viết tài liệu", owner="Tú", due_date=date(2026, 10, 20)),
        _e(6, ItemType.ACTION_ITEM, "Việc xa", owner="Tú", due_date=date(2026, 12, 1)),
        _e(7, ItemType.ACTION_ITEM, "Quá hạn lâu", owner="Tú", due_date=date(2026, 8, 1)),
        _e(8, ItemType.DECISION, "→ Redis Streams"),
        _e(9, ItemType.DECISION, "→ MongoDB", status=ItemStatus.SUPERSEDED, condition="x"),
    ]
    a = build_agenda(entries, today=TODAY, project="Thông báo", projects=["Thông báo"])
    assert [e.item_id for e in a.to_decide] == ["i1", "i2"]  # newest meeting first
    assert [e.item_id for e in a.conditions] == ["i3"]  # superseded decision left out
    assert [e.item_id for e in a.due] == ["i5", "i4"]  # by due date, far/old ones left out
    md = a.markdown
    assert md.startswith("**📋 Chương trình họp kế tiếp – Thông báo** (lập ngày 22/10/2026)")
    assert "• Ai làm dashboard? — người được giao đã từ chối (Quốc: “Tuần này em kín lịch rồi.”)" in md
    assert "Soạn mẫu tiếng Anh — điều kiện: pháp chế duyệt" in md
    assert "• Tú – Viết tài liệu – hạn 20/10/2026 (QUÁ HẠN)" in md
    assert "• Quốc – Dựng hàng đợi – hạn 22/10/2026 (hôm nay)" in md


def test_empty_agenda_says_so() -> None:
    a = build_agenda([], today=TODAY, project=None, projects=[])
    assert "Không còn việc tồn đọng" in a.markdown and "–" not in a.markdown.splitlines()[0]


def test_clip_cuts_at_a_line_break() -> None:
    text = "\n".join(f"dòng {i:04d} " + "x" * 40 for i in range(200))
    out = clip(text)
    assert len(out) <= DISCORD_LIMIT and out.endswith("\n…")
    assert all(line.startswith("dòng") for line in out.splitlines()[:-1])


def test_tasks_filter_by_owner_and_sort_by_urgency() -> None:
    entries = [
        _e(1, ItemType.ACTION_ITEM, "Không hạn", owner="Minh"),
        _e(2, ItemType.ACTION_ITEM, "Sắp tới", owner="minh", due_date=date(2026, 10, 25)),
        _e(3, ItemType.ACTION_ITEM, "Trễ", owner="Minh", due_date=date(2026, 10, 1)),
        _e(4, ItemType.ACTION_ITEM, "Của Hoa", owner="Hoa", due_date=TODAY),
        _e(5, ItemType.ACTION_ITEM, "Cũ", owner="Minh", status=ItemStatus.SUPERSEDED),
        _e(6, ItemType.DECISION, "→ Postgres", owner="Minh"),
    ]
    t = build_tasks(entries, owner="MINH", projects=[])
    assert [e.content for e in t.tasks] == ["Trễ", "Sắp tới", "Không hạn"]
    assert t.owners == ["Hoa", "Minh"]
    assert len(build_tasks(entries, owner=None, projects=[]).tasks) == 4


def test_tasks_message() -> None:
    t = build_tasks([_e(3, ItemType.ACTION_ITEM, "Trễ", owner="Minh", due_date=date(2026, 10, 1))],
                    owner="Minh", projects=[])
    msg = tasks_message(t, "Minh")
    assert msg.startswith("🗂️ **Việc của Minh** (1)")
    assert "• Trễ – hạn 01/10/2026 **(QUÁ HẠN)** · họp “Họp 3” 19/10/2026" in msg
    empty = tasks_message(build_tasks([_e(4, ItemType.ACTION_ITEM, "x", owner="Hoa")],
                                      owner="Lan", projects=[]), "Lan")
    assert "Không tìm thấy việc nào của **Lan**" in empty and "Hoa" in empty


def test_decision_log_newest_first_and_message_skips_superseded() -> None:
    entries = [
        _e(1, ItemType.DECISION, "CSDL? → MongoDB", meeting_date=date(2026, 10, 1),
           status=ItemStatus.SUPERSEDED, ts="00:01:00"),
        _e(2, ItemType.DECISION, "CSDL? → PostgreSQL", meeting_date=date(2026, 10, 8),
           supersedes=["MongoDB"], ts="00:03:30"),
        _e(3, ItemType.ACTION_ITEM, "Dựng schema"),
    ]
    d = build_decisions(entries, projects=[])
    assert [e.item_id for e in d.decisions] == ["i2", "i1"]
    msg = decisions_message(d, "Thanh toán")
    assert "• 08/10/2026 · CSDL? → PostgreSQL (thay cho: MongoDB)" in msg
    assert "MongoDB\n" not in msg and "→ MongoDB" not in msg
    assert "Chưa có quyết định" in decisions_message(build_decisions([], projects=[]), None)
