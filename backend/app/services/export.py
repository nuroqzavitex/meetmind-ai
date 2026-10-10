"""Pure rendering of published minutes (no DB access)."""

from datetime import date, datetime
from typing import Any

from app.ai.domain.enums import ItemStatus, ItemType, ReviewState
from app.ai.domain.models import MeetingContext, MeetingItem

_SECTIONS: list[tuple[ItemType, str]] = [
    (ItemType.DECISION, "Quyết định"),
    (ItemType.ACTION_ITEM, "Việc cần làm"),
    (ItemType.BLOCKER, "Vướng mắc"),
    (ItemType.REQUEST, "Yêu cầu"),
    (ItemType.OPEN_QUESTION, "Câu hỏi mở"),
    (ItemType.KNOWLEDGE, "Tri thức"),
    (ItemType.FEEDBACK, "Góp ý"),
]


def _publishable(items: list[MeetingItem]) -> list[MeetingItem]:
    return [
        i
        for i in items
        if i.review_state in (ReviewState.APPROVED, ReviewState.EDITED)
        and i.status != ItemStatus.SUPERSEDED
    ]


def _fmt(d: date | datetime) -> str:
    return d.strftime("%d/%m/%Y")


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _bullet(item: MeetingItem) -> str:
    line = f"- {_one_line(item.content)}"
    if item.owner:
        line += f" — {_one_line(item.owner)}"
    if item.due_date:
        line += f" (hạn {_fmt(item.due_date)})"
    if item.evidence:
        ev = item.evidence[0]
        line += f" [{ev.ts} {ev.speaker}]"
    if item.type == ItemType.DECISION and item.supersedes:
        line += f" (thay cho: {', '.join(item.supersedes)})"
    return line


def render_markdown(
    ctx: MeetingContext, items: list[MeetingItem], published_at: datetime | None
) -> str:
    kept = _publishable(items)
    lines = [f"# {ctx.title}", "", f"Ngày: {_fmt(ctx.meeting_date)} · Dự án: {ctx.project or '—'}"]
    for type_, heading in _SECTIONS:
        group = [i for i in kept if i.type == type_]
        if not group:
            continue
        lines += ["", f"## {heading}", ""]
        lines += [_bullet(i) for i in group]
    if published_at is not None:
        lines += ["", f"Phát hành: {_fmt(published_at)}"]
    return "\n".join(lines) + "\n"


def render_json(ctx: MeetingContext, items: list[MeetingItem]) -> dict[str, Any]:
    return {
        "meeting": ctx.model_dump(mode="json"),
        "items": [i.model_dump(mode="json") for i in _publishable(items)],
    }
