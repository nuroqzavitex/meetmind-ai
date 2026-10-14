import pytest

from app.ai.domain.enums import Act, OptState
from app.ai.domain.models import DialogueAct
from app.ai.domain.state_machine import Topic, run_topic

P, S, O, D = Act.PROPOSE, Act.SUPPORT, Act.OBJECT, Act.DECIDE
R, DF, RO = Act.REJECT, Act.DEFER, Act.REOPEN
PR, DI, DE, RJ, SU, OP = (
    OptState.PROPOSED, OptState.DISCUSSED, OptState.DECIDED,
    OptState.REJECTED, OptState.SUPERSEDED, OptState.OPEN,
)


def act(kind: Act, option: str | None, start: float, seq: int | None = None) -> DialogueAct:
    n = int(start) if seq is None else seq
    return DialogueAct(
        id=f"a{start}-{n}-{kind.value}", utterance_id=f"u{n}", seq=n, speaker="X",
        start=start, act=kind, quote="q", option=option,
    )


# (acts as (Act, option, start[, seq]), expected {label: (state, superseded_by)}, extras)
CASES: dict[str, tuple[list[tuple], dict[str, tuple[OptState, str | None]], dict]] = {
    "1_a_to_b": (
        [(P, "A", 1), (O, "A", 2), (P, "B", 3), (S, "B", 4), (D, "B", 5)],
        {"A": (SU, "B"), "B": (DE, None)}, {},
    ),
    "2_decide_a_then_b": (
        [(P, "A", 1), (D, "A", 2), (P, "B", 3), (D, "B", 4)],
        {"A": (SU, "B"), "B": (DE, None)}, {},
    ),
    "3_back_to_a": (
        [(D, "A", 1), (D, "B", 2), (D, "A", 3)],
        {"A": (DE, None), "B": (SU, "A")}, {},
    ),
    "4_reopen_no_decision": (
        [(P, "A", 1), (D, "B", 2), (RO, "B", 3)],
        {"A": (OP, None), "B": (OP, None)}, {},
    ),
    "5_nobody_decides": (
        [(P, "A", 1), (S, "A", 2)],
        {"A": (OP, None)}, {},
    ),
    "6_reject": (
        [(P, "A", 1), (R, "A", 2), (P, "B", 3), (D, "B", 4)],
        {"A": (RJ, None), "B": (DE, None)}, {},
    ),
    "7_defer": (
        [(P, "A", 1), (DF, None, 2)],
        {"A": (OP, None)}, {"deferred": True},
    ),
    "8_reject_decided": (
        [(P, "A", 1), (D, "B", 2), (R, "B", 3)],
        {"A": (OP, None), "B": (RJ, None)}, {},
    ),
    "9_decide_single_candidate": (
        [(P, "A", 1), (S, "A", 2), (D, None, 3)],
        {"A": (DE, None)}, {},
    ),
    "10_decide_ambiguous": (
        [(P, "A", 1), (P, "B", 2), (D, None, 3)],
        {"A": (OP, None), "B": (OP, None)}, {"ambiguous": 1},
    ),
    "11_same_ts": (
        [(D, "A", 5, 1), (D, "B", 5, 2)],
        {"A": (SU, "B"), "B": (DE, None)}, {},
    ),
    "13_bare_decide_after_defer": (
        [(P, "A", 1), (DF, None, 2), (D, None, 3)],
        {"A": (OP, None)}, {"deferred": True, "ambiguous": 1},
    ),
    "14_explicit_decide_settles_earlier_bare_one": (
        [(P, "A", 1), (P, "B", 2), (D, None, 3), (D, "B", 4)],
        {"A": (SU, "B"), "B": (DE, None)}, {},
    ),
    "12_support_superseded": (
        [(D, "A", 1), (D, "B", 2), (S, "A", 3)],
        {"A": (SU, "B"), "B": (DE, None)}, {},
    ),
}


@pytest.mark.parametrize("name", CASES)
def test_scenario(name: str) -> None:
    spec, expected, extras = CASES[name]
    acts = [act(*s) for s in spec]
    topic = run_topic(Topic(topic_id="t", question="q"), acts)

    for label, (state, sup) in expected.items():
        assert topic.options[label].state == state, label
        assert topic.options[label].superseded_by == sup, label

    assert topic.deferred is extras.get("deferred", False)
    assert len(topic.ambiguous_decides) == extras.get("ambiguous", 0)

    for opt in topic.options.values():
        assert len(opt.history) == len(opt.acts)
        attached = [a for a in acts if a.option == opt.label]
        # DECIDE without option may attach to a resolved label
        assert len(opt.acts) >= len(attached)


def test_decided_act_recorded() -> None:
    spec = CASES["1_a_to_b"][0]
    topic = run_topic(Topic(topic_id="t", question="q"), [act(*s) for s in spec])
    decided = topic.options["B"].decided_act
    assert decided is not None and decided.start == 5
