"""Agent 3d: arbitrate topics whose decisions look conflicting."""

from pydantic import BaseModel

from app.ai.domain.enums import Act, OptState
from app.ai.domain.models import DialogueAct, MeetingContext, Utterance
from app.ai.domain.names import norm_name
from app.ai.domain.state_machine import Topic
from app.ai.domain.timefmt import fmt_ts
from app.ai.llm import LLMClient, load_prompt

CLOSE_DECIDE_SECONDS = 60
CONTEXT_PAD = 3


class Arbitration(BaseModel):
    decided_option: str | None = None
    ambiguous: bool
    rationale: str


def _all_acts(topic: Topic) -> list[DialogueAct]:
    acts = [a for o in topic.options.values() for a in o.acts]
    return sorted(acts, key=lambda a: (a.start, a.seq))


def arbitration_reasons(
    topic: Topic, ctx: MeetingContext, acts: list[DialogueAct] | None = None
) -> list[str]:
    """Why ``topic`` needs arbitration; ``acts`` = all topic acts (default: option acts)."""
    reasons: list[str] = []
    acts = _all_acts(topic) if acts is None else sorted(acts, key=lambda a: (a.start, a.seq))

    decides = [(o.label, a) for o in topic.options.values() for a in o.acts if a.act == Act.DECIDE]
    if any(
        la != lb and abs(a.start - b.start) < CLOSE_DECIDE_SECONDS
        for i, (la, a) in enumerate(decides)
        for lb, b in decides[i + 1 :]
    ):
        reasons.append("close_decides")

    makers = {norm_name(p.name) for p in ctx.participants if p.is_decision_maker}
    if makers:
        for i, a in enumerate(acts[:-1]):
            if (
                a.act == Act.DECIDE
                and norm_name(a.speaker) not in makers
                and acts[i + 1].act == Act.OBJECT
            ):
                reasons.append("unauthorized_then_object")
                break

    for o in topic.options.values():
        if o.state == OptState.DECIDED and o.decided_act is not None:
            since = o.decided_act.start
            if any(a.act == Act.OBJECT and a.start > since for a in o.acts):
                reasons.append("object_after_decide")
                break
    return reasons


def _window(topic: Topic, utts: list[Utterance]) -> list[Utterance]:
    acts = _all_acts(topic)
    ordered = sorted(utts, key=lambda u: u.seq)
    if not acts or not ordered:
        return ordered
    lo, hi = min(a.seq for a in acts), max(a.seq for a in acts)
    idx = [i for i, u in enumerate(ordered) if lo <= u.seq <= hi]
    if not idx:
        return []
    return ordered[max(0, idx[0] - CONTEXT_PAD) : idx[-1] + 1 + CONTEXT_PAD]


def _render(topic: Topic, utts: list[Utterance], reasons: list[str]) -> str:
    lines = [
        f"Chủ đề: {topic.question}",
        "Lý do phân xử: " + ", ".join(reasons),
        "",
        "## Lịch sử phương án",
    ]
    for o in topic.options.values():
        state = o.state.value if o.state else "-"
        by = f", bị thay bởi {o.superseded_by}" if o.superseded_by else ""
        lines.append(f"- {o.label} (hiện: {state}{by})")
        lines.extend(f"    {fmt_ts(ts)} | {act} | {after}" for ts, act, after in o.history)
    lines += ["", "## Hội thoại"]
    lines.extend(f"{u.id} [{fmt_ts(u.start)}] {u.speaker}: {u.text}" for u in _window(topic, utts))
    return "\n".join(lines)


async def arbitrate(
    llm: LLMClient, topic: Topic, utts: list[Utterance], reasons: list[str], prompt_version: str
) -> Arbitration:
    system = load_prompt("arbitrate", prompt_version)
    return await llm.structured(
        agent="arbitrate", system=system, user=_render(topic, utts, reasons), schema=Arbitration
    )


def _make_ambiguous(topic: Topic) -> None:
    for o in topic.options.values():
        if o.state in (OptState.DECIDED, OptState.SUPERSEDED):
            o.state, o.superseded_by, o.decided_act = OptState.OPEN, None, None
    topic.needs_confirmation = True


def _find_label(topic: Topic, label: str | None) -> str | None:
    if label is None:
        return None
    key = label.strip().casefold()
    return next((k for k in topic.options if k.casefold() == key), None)


def _revoked_after(decide: DialogueAct, acts: list[DialogueAct]) -> bool:
    """True when a REJECT or REOPEN of the option follows its latest DECIDE."""
    since = (decide.start, decide.seq)
    return any(
        a.act in (Act.REJECT, Act.REOPEN) and (a.start, a.seq) > since for a in acts
    )


def apply_arbitration(topic: Topic, result: Arbitration) -> Topic:
    out = topic.model_copy(deep=True)
    label = _find_label(out, result.decided_option)
    if result.ambiguous or label is None:
        _make_ambiguous(out)
        return out
    target = out.options[label]
    if target.state == OptState.DECIDED:
        return out
    decides = [a for a in target.acts if a.act == Act.DECIDE]
    latest = max(decides, key=lambda a: (a.start, a.seq)) if decides else None
    if target.state == OptState.REJECTED or latest is None or _revoked_after(latest, target.acts):
        _make_ambiguous(out)
        return out
    target.decided_act = latest
    target.state, target.superseded_by = OptState.DECIDED, None
    for o in out.options.values():
        if o is not target and o.state != OptState.REJECTED:
            o.state, o.superseded_by, o.decided_act = OptState.SUPERSEDED, label, None
    return out
