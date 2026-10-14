"""Agent 3c: build MeetingItems and confidence from topics and dialogue acts (spec 8.3, 10.1)."""

from statistics import mean
from typing import Any

from rapidfuzz import fuzz

from app.ai.agents.topics import TopicSpec
from app.ai.domain.due_dates import resolve_due
from app.ai.domain.enums import Act, ItemStatus, ItemType, OptState
from app.ai.domain.models import DialogueAct, Evidence, MeetingContext, MeetingItem
from app.ai.domain.names import norm_name
from app.ai.domain.state_machine import Option, Topic
from app.ai.domain.timefmt import fmt_ts

NEEDS_CONFIRMATION = "needs_confirmation"
ASK_PERMISSION = "Xin ý kiến"
UNASSIGNED_DECIDE_PREFIX = "Cần xác nhận quyết định: "
SIMPLE_TYPES = {
    Act.RAISE_BLOCKER: ItemType.BLOCKER,
    Act.REQUEST: ItemType.REQUEST,
    Act.FEEDBACK: ItemType.FEEDBACK,
    Act.KNOWLEDGE: ItemType.KNOWLEDGE,
}
TASK_ACTS = {Act.ASSIGN, Act.ACCEPT_TASK}
SIMILAR = 80
ACCEPT_WINDOW = 2
ASK_ANSWER_WINDOW = 3
MAX_RATIONALE = 3


def decision_confidence(opt: Option, ctx: MeetingContext) -> float:
    a = opt.decided_act
    assert a is not None
    c = a.confidence
    makers = {norm_name(p.name) for p in ctx.participants if p.is_decision_maker}
    if makers and norm_name(a.speaker) not in makers:
        c *= 0.85  # người chốt không có thẩm quyền
    if any(x.act == Act.OBJECT and x.start > a.start for x in opt.acts):
        c *= 0.6  # có phản đối sau khi chốt
    return round(c, 2)


def _ev(a: DialogueAct) -> Evidence:
    return Evidence(
        utterance_id=a.utterance_id, speaker=a.speaker, ts=fmt_ts(a.start), quote=a.quote
    )


def _mean_conf(acts: list[DialogueAct]) -> float:
    return round(mean(a.confidence for a in acts), 2) if acts else 0.7


def decision_content(question: str, label: str) -> str:
    """`question → label`, or just `label` when the question is that option asked as yes/no."""
    q = norm_name(question.strip().rstrip("?").strip())
    if not q or q == norm_name(label):
        return label
    return f"{question} → {label}"


def _ask_permission(text: str) -> str:
    """Prefix "Xin ý kiến: " unless the text already starts with it (any case)."""
    body = text.strip()
    if body.casefold().startswith(ASK_PERMISSION.casefold()):
        return ASK_PERMISSION + body[len(ASK_PERMISSION) :]
    return f"{ASK_PERMISSION}: {body}"


def _order(a: DialogueAct) -> tuple[float, int]:
    return (a.start, a.seq)


def _topic_acts(topic: Topic, acts: list[DialogueAct]) -> list[DialogueAct]:
    seen: dict[str, DialogueAct] = {a.id: a for a in acts if a.topic_id == topic.topic_id}
    for o in topic.options.values():
        for a in o.acts:
            seen.setdefault(a.id, a)
    return sorted(seen.values(), key=_order)


def _group_tasks(tasks: list[DialogueAct]) -> list[list[DialogueAct]]:
    groups: list[list[DialogueAct]] = []
    for a in sorted(tasks, key=_order):
        target = None
        for g in groups:
            if _joins(a, g):
                target = g
                break
        if target is None:
            groups.append([a])
        else:
            target.append(a)
    return groups


def _joins(a: DialogueAct, group: list[DialogueAct]) -> bool:
    for m in group:
        if a.content and m.content and fuzz.token_set_ratio(a.content, m.content) >= SIMILAR:
            return True
        adjacent = a.act == Act.ACCEPT_TASK and m.act == Act.ASSIGN
        same_person = m.assignee is None or norm_name(m.assignee) == norm_name(a.speaker)
        if adjacent and same_person and 0 < a.seq - m.seq <= ACCEPT_WINDOW:
            return True
    return False


def build_items(
    ctx: MeetingContext,
    topics: list[Topic],
    specs: list[TopicSpec],
    acts: list[DialogueAct],
) -> list[MeetingItem]:
    questions = {s.topic_id: s.question for s in specs}
    # (start, seq) of first evidence, then insertion index; item.id filled later
    pending: list[tuple[tuple[float, int], MeetingItem]] = []

    def add(key_act: DialogueAct, **kw: Any) -> None:
        item = MeetingItem(id="", meeting_id=ctx.meeting_id, **kw)
        pending.append((_order(key_act), item))

    for topic in topics:
        question = topic.question or questions.get(topic.topic_id, "")
        t_acts = _topic_acts(topic, acts)
        decided = [o for o in topic.options.values() if o.state == OptState.DECIDED and o.decided_act]
        flag = [NEEDS_CONFIRMATION] if topic.ambiguous_decides else []

        for opt in decided:
            da = opt.decided_act
            assert da is not None
            evidence_acts = [da]
            first_propose = next(
                (x for x in sorted(opt.acts, key=_order) if x.act == Act.PROPOSE), None
            )
            if first_propose is not None and first_propose.id != da.id:
                evidence_acts.append(first_propose)
            quotes = [
                x.quote for x in sorted(opt.acts, key=_order)
                if x.act in (Act.SUPPORT, Act.OBJECT)
            ][:MAX_RATIONALE]
            add(
                da,
                type=ItemType.DECISION, topic_id=topic.topic_id,
                content=decision_content(question, opt.label),
                status=ItemStatus.FINAL,
                supersedes=[o.label for o in topic.options.values() if o.superseded_by == opt.label],
                rationale="; ".join(quotes) or None,
                owner=da.speaker, condition=da.condition,
                confidence=decision_confidence(opt, ctx), flags=list(flag),
                evidence=[_ev(x) for x in evidence_acts],
            )
            if da.condition:
                add(
                    da,
                    type=ItemType.OPEN_QUESTION, topic_id=topic.topic_id,
                    content=f"Theo dõi điều kiện: {da.condition}",
                    status=ItemStatus.OPEN, condition=da.condition,
                    confidence=_mean_conf([da]), evidence=[_ev(da)],
                )

        if decided:
            continue

        if t_acts:
            first = t_acts[0]
            add(
                first,
                type=ItemType.OPEN_QUESTION, topic_id=topic.topic_id, content=question,
                status=ItemStatus.OPEN, confidence=_mean_conf([first]),
                flags=[NEEDS_CONFIRMATION] if topic.needs_confirmation or flag else [],
                evidence=[_ev(first)],
            )
        for d in (x for x in t_acts if x.act == Act.DEFER and x.assignee):
            add(
                d,
                type=ItemType.ACTION_ITEM, topic_id=topic.topic_id,
                content=_ask_permission(d.content or question), owner=d.assignee,
                due_text=d.due_text, due_date=resolve_due(d.due_text, ctx.meeting_date) or d.due_date,
                confidence=_mean_conf([d]), evidence=[_ev(d)],
            )

    ordered = sorted(acts, key=_order)

    tasks = [a for a in ordered if a.act in TASK_ACTS]
    for group in _group_tasks(tasks):
        owners = [(a.assignee or (a.speaker if a.act == Act.ACCEPT_TASK else None)) for a in group]
        owner = next((o for o in reversed(owners) if o), None)
        due_a = next((a for a in reversed(group) if a.due_text), None)
        due_text = due_a.due_text if due_a else None
        due = resolve_due(due_text, ctx.meeting_date) if due_text else None
        if due is None:
            due = next((a.due_date for a in reversed(group) if a.due_date), None)
        content = next(
            (a.content for a in group if a.act == Act.ASSIGN and a.content),
            next((a.content for a in group if a.content), group[0].quote),
        )
        add(
            group[0],
            type=ItemType.ACTION_ITEM, topic_id=next((a.topic_id for a in group if a.topic_id), None),
            content=content, owner=owner, due_text=due_text, due_date=due,
            confidence=_mean_conf(group), evidence=[_ev(a) for a in group],
        )

    for a in ordered:
        if a.act in SIMPLE_TYPES:
            add(
                a,
                type=SIMPLE_TYPES[a.act], topic_id=a.topic_id,
                content=a.content or a.quote,
                requester=(a.assignee or a.speaker) if a.act == Act.REQUEST else None,
                confidence=_mean_conf([a]), evidence=[_ev(a)],
            )
        elif a.act == Act.DECIDE and a.topic_id is None:
            add(
                a,
                type=ItemType.OPEN_QUESTION,
                content=f"{UNASSIGNED_DECIDE_PREFIX}{a.content or a.quote}",
                status=ItemStatus.OPEN, confidence=_mean_conf([a]),
                flags=[NEEDS_CONFIRMATION], evidence=[_ev(a)],
            )
        elif a.act == Act.ASK and a.topic_id is None:
            answered = a.topic_hint is not None and any(
                b.act != Act.ASK and b.topic_hint == a.topic_hint
                and 0 < b.seq - a.seq <= ASK_ANSWER_WINDOW
                for b in ordered
            )
            if not answered:
                add(
                    a,
                    type=ItemType.OPEN_QUESTION, content=a.content or a.quote,
                    status=ItemStatus.OPEN, confidence=_mean_conf([a]), evidence=[_ev(a)],
                )

    # stable sort keeps decision before its follow-up question
    pending.sort(key=lambda p: p[0])
    items: list[MeetingItem] = []
    for n, (_, item) in enumerate(pending, start=1):
        items.append(item.model_copy(update={"id": f"{ctx.meeting_id}-i{n:03d}"}))
    return items
