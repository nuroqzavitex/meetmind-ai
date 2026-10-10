import unicodedata
from datetime import date

from app.ai.agents.arbitrate import Arbitration, apply_arbitration, arbitrate, arbitration_reasons
from app.ai.domain.enums import Act, OptState
from app.ai.domain.models import DialogueAct, MeetingContext, Participant, Utterance
from app.ai.domain.names import norm_name
from app.ai.domain.state_machine import Topic, run_topic
from app.ai.llm import FakeLLM

P, S, O, D = Act.PROPOSE, Act.SUPPORT, Act.OBJECT, Act.DECIDE


def ctx(makers: tuple[str, ...] = ()) -> MeetingContext:
    ps = [Participant(name=n, is_decision_maker=True) for n in makers]
    ps += [Participant(name="Minh"), Participant(name="Hoa")]
    return MeetingContext(meeting_id="m", title="t", meeting_date=date(2026, 10, 10), participants=ps)


CTX = ctx()


def act(kind: Act, option: str | None, start: float, speaker: str = "X") -> DialogueAct:
    n = int(start)
    return DialogueAct(
        id=f"a{n}", utterance_id=f"u{n}", seq=n, speaker=speaker, start=start, act=kind, quote="q", option=option
    )


def topic_of(spec: list[tuple]) -> Topic:
    return run_topic(Topic(topic_id="t1", question="Q?"), [act(*s) for s in spec])


def amb(opt: str | None, ambiguous: bool = False) -> Arbitration:
    return Arbitration(decided_option=opt, ambiguous=ambiguous, rationale="r")


def test_norm_name():
    assert norm_name("  LAN  ") == norm_name("lan") == "lan"
    assert norm_name("Nguyễn   Văn  A") == "nguyễn văn a"


def test_reasons_close_decides():
    assert "close_decides" in arbitration_reasons(topic_of([(D, "A", 10), (D, "B", 40)]), CTX)


def test_reasons_far_decides_not_close():
    assert "close_decides" not in arbitration_reasons(topic_of([(D, "A", 10), (D, "B", 100)]), CTX)


def test_reasons_none_for_clean_a_to_b():
    t = topic_of([(P, "A", 1), (O, "A", 2), (P, "B", 3), (S, "B", 4), (D, "B", 5)])
    assert arbitration_reasons(t, CTX) == []


def test_reasons_object_after_decide():
    assert arbitration_reasons(topic_of([(D, "A", 10), (O, "A", 20)]), CTX) == ["object_after_decide"]


def test_reasons_unauthorized_then_object():
    t = topic_of([(P, "A", 5), (D, "A", 10, "Minh"), (O, "A", 20, "Hoa")])
    assert arbitration_reasons(t, ctx(("Lan",))) == ["unauthorized_then_object", "object_after_decide"]


def test_unauthorized_requires_maker_and_non_maker_speaker():
    t = topic_of([(D, "A", 10, "Minh"), (O, "A", 20, "Hoa")])
    assert "unauthorized_then_object" not in arbitration_reasons(t, CTX)
    t2 = topic_of([(D, "A", 10, " lan "), (O, "A", 20, "Hoa")])
    assert "unauthorized_then_object" not in arbitration_reasons(t2, ctx(("Lan",)))


def test_unauthorized_object_must_be_immediately_next():
    t = topic_of([(D, "A", 10, "Minh"), (S, "A", 15), (O, "A", 20)])
    assert "unauthorized_then_object" not in arbitration_reasons(t, ctx(("Lan",)))


def test_apply_ambiguous_opens_all_without_mutating_input():
    t = topic_of([(P, "A", 1), (D, "A", 10), (D, "B", 40)])
    out = apply_arbitration(t, amb(None, True))
    assert {o.state for o in out.options.values()} == {OptState.OPEN}
    assert all(o.superseded_by is None for o in out.options.values())
    assert out.needs_confirmation is True
    assert t.options["B"].state == OptState.DECIDED and t.needs_confirmation is False


def test_apply_unknown_option_is_ambiguous():
    t = topic_of([(D, "A", 10)])
    out = apply_arbitration(t, amb("Z"))
    assert out.options["A"].state == OptState.OPEN and out.needs_confirmation


def test_apply_switch_decision():
    t = topic_of([(D, "B", 10), (D, "A", 40)])
    out = apply_arbitration(t, amb("B"))
    assert out.options["B"].state == OptState.DECIDED
    assert out.options["B"].decided_act is not None and out.options["B"].decided_act.start == 10
    assert out.options["A"].state == OptState.SUPERSEDED and out.options["A"].superseded_by == "B"
    assert not out.needs_confirmation
    assert t.options["A"].state == OptState.DECIDED


def test_apply_same_option_keeps():
    t = topic_of([(P, "C", 1), (S, "C", 2), (Act.REJECT, "C", 3), (D, "A", 10)])
    assert apply_arbitration(t, amb("A")) == t


def test_apply_option_without_decide_is_ambiguous():
    t = topic_of([(P, "B", 1), (D, "A", 10)])
    out = apply_arbitration(t, amb("B"))
    assert out.needs_confirmation and out.options["A"].state == OptState.OPEN


async def test_arbitrate_calls_llm_with_opus_agent_name():
    t = topic_of([(D, "A", 10), (O, "A", 20)])
    utts = [Utterance(id=f"u{i}", seq=i, speaker="X", start=float(i), text=f"câu {i}") for i in range(40)]
    llm = FakeLLM({"arbitrate": [{"decided_option": "A", "ambiguous": False, "rationale": "ok"}]})
    res = await arbitrate(llm, t, utts, ["object_after_decide"], "v1")
    assert res.decided_option == "A"
    agent, user = llm.calls[0]
    assert agent == "arbitrate"
    assert "u7 " in user and "u6 " not in user and "u23 " in user and "u24 " not in user
    assert "object_after_decide" in user


def test_norm_name_nfd_equals_nfc():
    assert norm_name(unicodedata.normalize("NFD", "Lan Hương")) == norm_name("Lan Hương")


R, REOPEN = Act.REJECT, Act.REOPEN


def test_reasons_close_decides_boundary_60s():
    assert "close_decides" not in arbitration_reasons(topic_of([(D, "A", 10), (D, "B", 70)]), CTX)
    assert "close_decides" in arbitration_reasons(topic_of([(D, "A", 10), (D, "B", 69)]), CTX)


def test_reasons_optionless_object_after_unauthorized_decide():
    spec = [(P, "A", 5), (D, "A", 10, "Minh"), (O, None, 20, "Hoa")]
    t = topic_of(spec)
    acts = [act(*s) for s in spec]
    assert "unauthorized_then_object" not in arbitration_reasons(t, ctx(("Lan",)))
    assert "unauthorized_then_object" in arbitration_reasons(t, ctx(("Lan",)), acts)


def test_apply_cannot_revive_rejected_option():
    # probe (a): PROPOSE A, DECIDE B by non-maker, OBJECT B, REJECT B -> LLM "B"
    t = topic_of([(P, "A", 1), (D, "B", 10, "Minh"), (O, "B", 20, "Hoa"), (R, "B", 30, "Lan")])
    assert t.options["B"].state == OptState.REJECTED
    out = apply_arbitration(t, amb("B"))
    assert out.needs_confirmation
    assert out.options["B"].state == OptState.REJECTED
    assert all(o.state != OptState.DECIDED for o in out.options.values())


def test_apply_rejected_after_decide_is_ambiguous():
    # probe (b): DECIDE A, DECIDE B +30s, REJECT A -> LLM "A"
    t = topic_of([(D, "A", 10), (D, "B", 40), (R, "A", 50)])
    out = apply_arbitration(t, amb("A"))
    assert out.needs_confirmation
    assert out.options["A"].state == OptState.REJECTED
    assert out.options["B"].state == OptState.OPEN


def test_apply_reopened_after_decide_is_ambiguous():
    # probe (c): DECIDE A, DECIDE B, REOPEN B -> LLM "B"
    t = topic_of([(D, "A", 10), (D, "B", 40), (REOPEN, "B", 50)])
    out = apply_arbitration(t, amb("B"))
    assert out.needs_confirmation
    assert all(o.state != OptState.DECIDED for o in out.options.values())


def test_apply_label_matched_case_insensitively():
    t = topic_of([(D, "Postgres", 10), (D, "MongoDB", 40)])
    out = apply_arbitration(t, amb("postgres"))
    assert out.options["Postgres"].state == OptState.DECIDED and not out.needs_confirmation
    assert out.options["MongoDB"].superseded_by == "Postgres"


def test_rejected_options_untouched_in_switch_and_ambiguous():
    t = topic_of([(P, "C", 1), (R, "C", 2), (D, "B", 10), (D, "A", 40)])
    switched = apply_arbitration(t, amb("B"))
    assert switched.options["B"].state == OptState.DECIDED
    assert switched.options["C"].state == OptState.REJECTED
    assert switched.options["C"].superseded_by is None
    ambiguous = apply_arbitration(t, amb(None, True))
    assert ambiguous.options["C"].state == OptState.REJECTED
