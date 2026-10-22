"""Cross-meeting views of published minutes: next-meeting agenda, tasks per person, decision log.

Everything here is assembled from reviewed items with plain code (no LLM), so it is instant,
free and identical on every run.
"""

from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.domain.enums import ItemStatus, ItemType
from app.ai.domain.models import MeetingItem
from app.ai.domain.names import norm_name
from app.ai.retrieval.indexing import HOLD_LABELS
from app.core.auth import Principal
from app.core.errors import Conflict
from app.models import Item, Meeting
from app.notify.discord import DiscordClient, DiscordError
from app.repositories import org_settings as settings_repo
from app.repositories import overview as repo
from app.schemas.overview import AgendaOut, DecisionsOut, DueState, OverviewEntry, TasksOut

VN_TZ = timezone(timedelta(hours=7))
SOON_DAYS = 7  # "due soon" on the agenda
OVERDUE_DAYS = 30  # older overdue tasks are dropped from the agenda (they live in "Việc")
AGENDA_LIMIT = 15  # entries per agenda section
DISCORD_LIMIT = 1900  # Discord rejects messages over 2000 characters


def vn_today() -> date:
    """Due dates are Vietnamese calendar days."""
    return datetime.now(UTC).astimezone(VN_TZ).date()


def due_state(due: date | None, today: date) -> DueState | None:
    if due is None:
        return None
    if due < today:
        return "overdue"
    if due == today:
        return "today"
    return "soon" if due <= today + timedelta(days=SOON_DAYS) else "later"


def entry(meeting: Meeting, model: MeetingItem, today: date) -> OverviewEntry:
    ev = model.evidence[0] if model.evidence else None
    return OverviewEntry(
        item_id=model.id, meeting_id=meeting.id, meeting_title=meeting.title,
        meeting_date=meeting.meeting_date, project=meeting.project, type=model.type,
        status=model.status, content=model.content, owner=model.owner, due_date=model.due_date,
        due_state=due_state(model.due_date, today) if model.type == ItemType.ACTION_ITEM else None,
        condition=model.condition, supersedes=model.supersedes, hold=model.hold,
        speaker=ev.speaker if ev else None, ts=ev.ts if ev else None,
        quote=ev.quote if ev else None, utterance_id=ev.utterance_id if ev else None,
    )


def _entries(rows: list[tuple[Meeting, Item]], today: date) -> list[OverviewEntry]:
    return [entry(m, MeetingItem.model_validate(i.data), today) for m, i in rows]


def _current(e: OverviewEntry) -> bool:
    return e.status != ItemStatus.SUPERSEDED


def _fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def build_agenda(
    entries: list[OverviewEntry], *, today: date, project: str | None, projects: list[str]
) -> AgendaOut:
    live = [e for e in entries if _current(e)]
    newest_first = sorted(live, key=lambda e: e.meeting_date, reverse=True)
    to_decide = [e for e in newest_first if e.type == ItemType.OPEN_QUESTION]
    conditions = [
        e for e in newest_first
        if e.type in (ItemType.DECISION, ItemType.ACTION_ITEM) and e.condition
    ]
    due = sorted(
        (
            e for e in live
            if e.type == ItemType.ACTION_ITEM and e.due_date is not None
            and today - timedelta(days=OVERDUE_DAYS) <= e.due_date <= today + timedelta(days=SOON_DAYS)
        ),
        key=lambda e: (e.due_date, e.owner or ""),
    )
    agenda = AgendaOut(
        project=project, projects=projects, generated_on=today,
        to_decide=to_decide[:AGENDA_LIMIT], conditions=conditions[:AGENDA_LIMIT],
        due=due[:AGENDA_LIMIT], markdown="",
    )
    return agenda.model_copy(update={"markdown": agenda_markdown(agenda)})


def _why(e: OverviewEntry) -> str:
    if e.hold:
        who = f"{e.hold.speaker}: " if e.hold.speaker else ""
        return f" — {HOLD_LABELS[e.hold.reason]} ({who}“{e.hold.quote}”)"
    return ""


def agenda_markdown(a: AgendaOut) -> str:
    """Plain text that pastes well into chat (and fits a Discord message)."""
    title = f"📋 Chương trình họp kế tiếp{f' – {a.project}' if a.project else ''}"
    lines = [f"**{title}** (lập ngày {_fmt(a.generated_on)})"]
    if a.to_decide:
        lines += ["", "**1. Cần quyết định**"]
        lines += [
            f"• {e.content}{_why(e)} · họp {_fmt(e.meeting_date)}" for e in a.to_decide
        ]
    if a.conditions:
        lines += ["", "**2. Theo dõi điều kiện**"]
        lines += [
            f"• {e.content} — điều kiện: {e.condition} · họp {_fmt(e.meeting_date)}"
            for e in a.conditions
        ]
    if a.due:
        lines += ["", "**3. Việc quá hạn và sắp đến hạn**"]
        labels = {"overdue": "QUÁ HẠN", "today": "hôm nay", "soon": "sắp đến hạn", "later": ""}
        for e in a.due:
            assert e.due_date is not None
            lines.append(
                f"• {e.owner or 'Chưa có người nhận'} – {e.content} – hạn {_fmt(e.due_date)}"
                f" ({labels[e.due_state or 'later']})"
            )
    if not (a.to_decide or a.conditions or a.due):
        lines += ["", "Không còn việc tồn đọng: mọi thứ trong các cuộc họp đã phát hành đều đã chốt."]
    return clip("\n".join(lines))


def clip(text: str, limit: int = DISCORD_LIMIT) -> str:
    """Cut at a line break so a message never ends mid-sentence."""
    if len(text) <= limit:
        return text
    cut = text.rfind("\n", 0, limit - 2)
    return text[: cut if cut > 0 else limit - 2] + "\n…"


def build_tasks(entries: list[OverviewEntry], *, owner: str | None, projects: list[str]) -> TasksOut:
    tasks = [e for e in entries if e.type == ItemType.ACTION_ITEM and _current(e)]
    owners: dict[str, str] = {}
    for e in tasks:
        if e.owner:
            owners.setdefault(norm_name(e.owner), e.owner)
    if owner:
        who = norm_name(owner)
        tasks = [e for e in tasks if e.owner and norm_name(e.owner) == who]
    order = {"overdue": 0, "today": 1, "soon": 2, "later": 3}
    tasks.sort(key=lambda e: (
        order.get(e.due_state or "", 4), e.due_date or date.max, -e.meeting_date.toordinal(),
    ))
    return TasksOut(projects=projects, owners=sorted(owners.values(), key=norm_name), tasks=tasks)


def build_decisions(entries: list[OverviewEntry], *, projects: list[str]) -> DecisionsOut:
    decisions = [e for e in entries if e.type == ItemType.DECISION]
    decisions.sort(key=lambda e: (e.meeting_date, e.ts or ""), reverse=True)
    return DecisionsOut(projects=projects, decisions=decisions)


async def _load(
    session: AsyncSession, org_id: str, project: str | None, today: date
) -> tuple[list[OverviewEntry], list[str]]:
    rows = await repo.published_items(session, org_id=org_id, project=project)
    return _entries(rows, today), await repo.projects(session, org_id=org_id)


async def agenda_for(
    session: AsyncSession, *, org_id: str, project: str | None, today: date
) -> AgendaOut:
    entries, projects = await _load(session, org_id, project, today)
    return build_agenda(entries, today=today, project=project, projects=projects)


async def get_agenda(
    session: AsyncSession, *, principal: Principal, project: str | None, today: date
) -> AgendaOut:
    return await agenda_for(session, org_id=principal.org_id, project=project, today=today)


async def get_tasks(
    session: AsyncSession, *, principal: Principal, project: str | None, owner: str | None,
    today: date,
) -> TasksOut:
    entries, projects = await _load(session, principal.org_id, project, today)
    return build_tasks(entries, owner=owner, projects=projects)


async def get_decisions(
    session: AsyncSession, *, principal: Principal, project: str | None, today: date
) -> DecisionsOut:
    entries, projects = await _load(session, principal.org_id, project, today)
    return build_decisions(entries, projects=projects)


async def send_agenda(
    session: AsyncSession, discord: DiscordClient, *, principal: Principal, project: str | None,
    today: date,
) -> None:
    row = await settings_repo.get(session, org_id=principal.org_id)
    if row is None or row.discord_webhook_url is None:
        raise Conflict("Tổ chức chưa cấu hình webhook Discord", "no_webhook")
    agenda = await get_agenda(session, principal=principal, project=project, today=today)
    try:
        await discord.send(row.discord_webhook_url, {
            "content": agenda.markdown, "allowed_mentions": {"parse": []},
        })
    except DiscordError as exc:
        raise Conflict("Discord không nhận tin nhắn, kiểm tra lại webhook", "discord_error") from exc


TASK_LINES = 15
DECISION_LINES = 10


def tasks_message(t: TasksOut, who: str) -> str:
    if not t.tasks:
        known = ", ".join(t.owners[:12]) or "chưa có"
        return (f"Không tìm thấy việc nào của **{who}** trong các cuộc họp đã phát hành. "
                f"Tên cần giống tên trong biên bản: {known}.")
    labels = {"overdue": " **(QUÁ HẠN)**", "today": " (hôm nay)", "soon": "", "later": ""}
    lines = [f"🗂️ **Việc của {t.tasks[0].owner}** ({len(t.tasks)})"]
    for e in t.tasks[:TASK_LINES]:
        due = f" – hạn {_fmt(e.due_date)}{labels[e.due_state or 'later']}" if e.due_date else ""
        lines.append(f"• {e.content}{due} · họp “{e.meeting_title}” {_fmt(e.meeting_date)}")
    return clip("\n".join(lines))


def decisions_message(d: DecisionsOut, project: str | None) -> str:
    final = [e for e in d.decisions if _current(e)]
    title = f"🧭 **Quyết định gần đây{f' – {project}' if project else ''}**"
    if not final:
        return f"{title}\nChưa có quyết định nào trong các cuộc họp đã phát hành."
    lines = [title]
    for e in final[:DECISION_LINES]:
        replaced = f" (thay cho: {', '.join(e.supersedes)})" if e.supersedes else ""
        lines.append(f"• {_fmt(e.meeting_date)} · {e.content}{replaced}")
    return clip("\n".join(lines))


async def command_message(
    session: AsyncSession, *, org_id: str, command: str, project: str | None, who: str | None,
    today: date,
) -> str:
    """Text answer of the Discord /chuongtrinh, /viec and /quyetdinh commands."""
    entries, projects = await _load(session, org_id, project, today)
    if command == "viec":
        return tasks_message(build_tasks(entries, owner=who, projects=projects), who or "")
    if command == "quyetdinh":
        return decisions_message(build_decisions(entries, projects=projects), project)
    return build_agenda(entries, today=today, project=project, projects=projects).markdown
