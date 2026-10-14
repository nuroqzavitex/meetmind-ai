"""Pure rendering of Discord messages (no I/O)."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from app.ai.domain.enums import ItemType
from app.ai.domain.models import MeetingContext, MeetingItem
from app.schemas.join_requests import JoinRequestOut
from app.services.export import publishable

COLOR = 0x4F46E5  # indigo, matches the UI primary
MAX_LINES = 10
MAX_LINE = 180
MAX_FIELD = 1024
OVERDUE_DAYS = 7
UPCOMING_DAYS = 2


def _fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _field(name: str, lines: list[str]) -> dict[str, Any]:
    """At most MAX_LINES whole lines, kept under Discord's 1024-character field limit."""
    out: list[str] = []
    size = 0
    for line in lines:
        if len(out) == MAX_LINES or size + len(line) + 1 > MAX_FIELD - 30:
            out.append(f"… và {len(lines) - len(out)} mục khác")
            break
        out.append(line)
        size += len(line) + 1
    return {"name": name, "value": "\n".join(out)}


def _task_line(item: MeetingItem, *, with_due: bool = True) -> str:
    who = f"**{_clip(item.owner, 40)}** – " if item.owner else ""
    due = f" (hạn {_fmt(item.due_date)})" if with_due and item.due_date else ""
    return _clip(f"• {who}{item.content}", MAX_LINE) + due


def connected_message() -> dict[str, Any]:
    return {
        "username": "MeetMind AI",
        "embeds": [
            {
                "title": "MeetMind đã kết nối",
                "description": "Kênh này sẽ nhận tóm tắt khi cuộc họp được phát hành"
                " và bản tin nhắc việc lúc 8h sáng (nếu bật).",
                "color": COLOR,
            }
        ],
    }


def published_message(
    ctx: MeetingContext, items: list[MeetingItem], minutes_url: str
) -> dict[str, Any]:
    kept = publishable(items)
    decisions = [i for i in kept if i.type == ItemType.DECISION]
    tasks = [i for i in kept if i.type == ItemType.ACTION_ITEM]
    questions = [i for i in kept if i.type == ItemType.OPEN_QUESTION]
    fields = []
    if decisions:
        fields.append(_field(f"✅ Quyết định ({len(decisions)})",
                             [_clip(f"• {i.content}", MAX_LINE) for i in decisions]))
    if tasks:
        fields.append(_field(f"📝 Việc cần làm ({len(tasks)})", [_task_line(i) for i in tasks]))
    if questions:
        fields.append({"name": "❓ Câu hỏi mở", "value": f"{len(questions)} câu hỏi chưa có lời đáp"})
    if not fields:
        fields.append({"name": "Nội dung", "value": "Cuộc họp không có quyết định hay việc cần làm."})
    meta = f"Ngày họp {_fmt(ctx.meeting_date)}" + (f" · Dự án {ctx.project}" if ctx.project else "")
    return {
        "username": "MeetMind AI",
        "content": "📢 Biên bản họp mới đã được phát hành",
        "embeds": [
            {
                "title": _clip(ctx.title, 250),
                "url": minutes_url,
                "description": meta,
                "color": COLOR,
                "fields": fields,
            }
        ],
    }


def join_request_message(request: JoinRequestOut, settings_url: str) -> dict[str, Any]:
    who = _clip(request.user_name, 80)
    if request.user_email:
        who += f" ({_clip(request.user_email, 80)})"
    return {
        "username": "MeetMind AI",
        "embeds": [
            {
                "title": "🙋 Có người xin vào tổ chức",
                "url": settings_url,
                "description": f"**{who}** xin tham gia **{_clip(request.org_name, 80)}**.\n"
                "Admin mở trang Cài đặt để đồng ý hoặc từ chối.",
                "color": COLOR,
            }
        ],
    }


@dataclass(frozen=True)
class DueTask:
    item: MeetingItem
    meeting_id: str
    meeting_title: str


@dataclass
class Digest:
    overdue: list[DueTask] = field(default_factory=list)
    today: list[DueTask] = field(default_factory=list)
    upcoming: list[DueTask] = field(default_factory=list)

    def empty(self) -> bool:
        return not (self.overdue or self.today or self.upcoming)


def select_digest(tasks: list[DueTask], today: date) -> Digest:
    """Bucket action items by due date relative to `today`; others are dropped."""
    digest = Digest()
    for t in sorted(tasks, key=lambda t: (t.item.due_date or today, t.meeting_title)):
        due = t.item.due_date
        if due is None or t.item.type != ItemType.ACTION_ITEM or not publishable([t.item]):
            continue
        if today - timedelta(days=OVERDUE_DAYS) <= due < today:
            digest.overdue.append(t)
        elif due == today:
            digest.today.append(t)
        elif today < due <= today + timedelta(days=UPCOMING_DAYS):
            digest.upcoming.append(t)
    return digest


def _digest_line(t: DueTask, with_due: bool) -> str:
    return f"{_task_line(t.item, with_due=with_due)} · _{_clip(t.meeting_title, 50)}_"


def digest_message(digest: Digest, today: date, app_url: str) -> dict[str, Any]:
    fields = []
    if digest.overdue:
        fields.append(_field(f"⚠️ Quá hạn ({len(digest.overdue)})",
                             [_digest_line(t, True) for t in digest.overdue]))
    if digest.today:
        fields.append(_field(f"📌 Đến hạn hôm nay ({len(digest.today)})",
                             [_digest_line(t, False) for t in digest.today]))
    if digest.upcoming:
        fields.append(_field(f"🗓️ Sắp đến hạn ({len(digest.upcoming)})",
                             [_digest_line(t, True) for t in digest.upcoming]))
    return {
        "username": "MeetMind AI",
        "embeds": [
            {
                "title": f"Nhắc việc ngày {_fmt(today)}",
                "url": app_url,
                "color": COLOR,
                "fields": fields,
            }
        ],
    }
