"""Topic state machine: decides the final state of each option in a topic."""

from pydantic import BaseModel

from app.ai.domain.enums import Act, OptState
from app.ai.domain.models import DialogueAct


class Option(BaseModel):
    label: str
    state: OptState | None = None
    superseded_by: str | None = None
    decided_act: DialogueAct | None = None
    acts: list[DialogueAct] = []
    history: list[tuple[float, str, str]] = []  # (ts, act, state_after)


class Topic(BaseModel):
    topic_id: str
    question: str
    options: dict[str, Option] = {}
    deferred: bool = False
    ambiguous_decides: list[DialogueAct] = []
    needs_confirmation: bool = False


DISCUSS = {Act.SUPPORT, Act.OBJECT, Act.AMEND}
INACTIVE = {OptState.REJECTED, OptState.SUPERSEDED}


def _restore_superseded_by(topic: Topic, label: str) -> None:
    for o in topic.options.values():
        if o.superseded_by == label:
            o.state, o.superseded_by = OptState.DISCUSSED, None


def _resolve_option(topic: Topic) -> str | None:
    """DECIDE không có option: chỉ gán khi có đúng một phương án còn hiệu lực."""
    active = [o.label for o in topic.options.values() if o.state not in INACTIVE]
    return active[0] if len(active) == 1 else None


def run_topic(topic: Topic, acts: list[DialogueAct]) -> Topic:
    for a in sorted(acts, key=lambda x: (x.start, x.seq)):
        label = a.option
        if label is None and a.act == Act.DECIDE:
            # After a deferral ("chờ ý kiến sếp"), a bare "ok" is not a decision on the only option.
            label = None if topic.deferred else _resolve_option(topic)
            if label is None:
                topic.ambiguous_decides.append(a)
                continue
        if label is None:
            if a.act == Act.DEFER:
                topic.deferred = True
            continue

        opt = topic.options.setdefault(label, Option(label=label))
        opt.acts.append(a)

        if a.act == Act.PROPOSE and opt.state is None:
            opt.state = OptState.PROPOSED
        elif a.act in DISCUSS and opt.state in (None, OptState.PROPOSED):
            opt.state = OptState.DISCUSSED
        elif a.act == Act.DECIDE:
            opt.state, opt.decided_act, opt.superseded_by = OptState.DECIDED, a, None
            # An explicit decision settles the unnamed "chốt" said before it.
            topic.ambiguous_decides = []
            for o in topic.options.values():
                if o is not opt and o.state != OptState.REJECTED:
                    o.state, o.superseded_by = OptState.SUPERSEDED, opt.label
        elif a.act == Act.REJECT:
            if opt.state == OptState.DECIDED:
                opt.decided_act = None
                _restore_superseded_by(topic, opt.label)
            opt.state, opt.superseded_by = OptState.REJECTED, None
        elif a.act == Act.REOPEN and opt.state == OptState.DECIDED:
            opt.state, opt.decided_act = OptState.DISCUSSED, None
            _restore_superseded_by(topic, opt.label)
        elif a.act == Act.DEFER:
            topic.deferred = True
        # PROPOSE/SUPPORT/OBJECT/AMEND trên phương án đã SUPERSEDED/REJECTED:
        # chỉ ghi lịch sử, không đổi trạng thái (chỉ DECIDE/REOPEN mới đổi được).

        opt.history.append((a.start, a.act.value, opt.state.value if opt.state else "-"))

    if not any(o.state == OptState.DECIDED for o in topic.options.values()):
        for o in topic.options.values():
            if o.state in (None, OptState.PROPOSED, OptState.DISCUSSED):
                o.state = OptState.OPEN
    return topic
