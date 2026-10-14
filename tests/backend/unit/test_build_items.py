from datetime import date

import pytest

from app.ai.agents.build_items import build_items, decision_confidence, decision_content
from app.ai.agents.topics import TopicSpec
from app.ai.domain.enums import Act, ItemStatus, ItemType, OptState
from app.ai.domain.models import DialogueAct, MeetingContext, Participant
from app.ai.domain.state_machine import Option, Topic, run_topic

CTX_0810 = MeetingContext(
    meeting_id="m1", title="t", meeting_date=date(2026, 10, 8),
    participants=[Participant(name="Lan", is_decision_maker=True), Participant(name="Minh")],
)
CTX_MAKER_LAN = CTX_0810
SPEC = TopicSpec(topic_id="t1", question="Dùng DB nào?")


def mk(n: int, kind: Act, speaker: str = "Minh", **kw) -> DialogueAct:
    return DialogueAct(
        id=f"a{n}", utterance_id=f"u{n}", seq=n, speaker=speaker, start=float(n * 10),
        act=kind, quote=kw.pop("quote", f"q{n}"), **kw,
    )


def topic_of(acts: list[DialogueAct]) -> Topic:
    return run_topic(Topic(topic_id="t1", question=SPEC.question), acts)


def types(items) -> list[ItemType]:
    return [i.type for i in items]


def test_decided_topic_makes_final_decision_with_supersedes():
    acts = [
        mk(1, Act.PROPOSE, option="MongoDB", topic_id="t1", quote="dùng Mongo"),
        mk(2, Act.PROPOSE, option="Postgres", topic_id="t1", quote="dùng Postgres"),
        mk(3, Act.SUPPORT, option="Postgres", topic_id="t1", quote="ok vì quan hệ"),
        mk(4, Act.DECIDE, "Lan", option="Postgres", topic_id="t1", quote="chốt Postgres"),
    ]
    items = build_items(CTX_0810, [topic_of(acts)], [SPEC], acts)
    [d] = items
    assert d.type == ItemType.DECISION and d.status == ItemStatus.FINAL
    assert d.content == "Dùng DB nào? → Postgres"
    assert d.owner == "Lan" and d.supersedes == ["MongoDB"]
    assert d.rationale == "ok vì quan hệ"
    assert d.id == "m1-i001" and d.topic_id == "t1"
    assert [e.quote for e in d.evidence] == ["chốt Postgres", "dùng Postgres"]
    assert d.evidence[0].ts == "00:00:40"
    assert d.confidence == 0.7


def test_undecided_topic_makes_open_question():
    acts = [
        mk(1, Act.PROPOSE, option="A", topic_id="t1"),
        mk(2, Act.SUPPORT, option="A", topic_id="t1"),
    ]
    [q] = build_items(CTX_0810, [topic_of(acts)], [SPEC], acts)
    assert q.type == ItemType.OPEN_QUESTION and q.status == ItemStatus.OPEN
    assert q.content == SPEC.question and q.evidence[0].utterance_id == "u1"
    assert q.flags == []


def test_conditional_decision_adds_followup_question():
    acts = [
        mk(1, Act.DECIDE, "Lan", option="A", topic_id="t1", condition="nếu ngân sách duyệt"),
    ]
    items = build_items(CTX_0810, [topic_of(acts)], [SPEC], acts)
    assert types(items) == [ItemType.DECISION, ItemType.OPEN_QUESTION]
    assert items[0].condition == "nếu ngân sách duyệt"
    assert items[1].content == "Theo dõi điều kiện: nếu ngân sách duyệt"
    assert items[1].status == ItemStatus.OPEN


def test_defer_makes_question_and_ask_permission_task():
    acts = [
        mk(1, Act.PROPOSE, option="A", topic_id="t1"),
        mk(2, Act.DEFER, "Lan", option="A", topic_id="t1", assignee="Minh",
           due_text="ngày mai"),
    ]
    items = build_items(CTX_0810, [topic_of(acts)], [SPEC], acts)
    assert types(items) == [ItemType.OPEN_QUESTION, ItemType.ACTION_ITEM]
    ai = items[1]
    assert ai.content == "Xin ý kiến: Dùng DB nào?" and ai.owner == "Minh"
    assert ai.due_date == date(2026, 10, 9)


def test_defer_self_claim_uses_defer_content_and_speaker_owner():
    acts = [
        mk(1, Act.DEFER, "Lan", topic_id="t1", assignee="Lan",
           content="xin ý kiến anh Tuấn về replica đọc"),
    ]
    items = build_items(CTX_0810, [topic_of(acts)], [SPEC], acts)
    ai = items[1]
    assert ai.type == ItemType.ACTION_ITEM and ai.owner == "Lan"
    assert ai.content == "Xin ý kiến anh Tuấn về replica đọc"


def test_defer_content_with_uppercase_prefix_not_doubled():
    acts = [mk(1, Act.DEFER, "Lan", topic_id="t1", assignee="Lan", content="Xin Ý Kiến sếp")]
    assert build_items(CTX_0810, [topic_of(acts)], [SPEC], acts)[1].content == "Xin ý kiến sếp"


def test_defer_without_assignee_makes_only_question():
    acts = [mk(1, Act.DEFER, "Lan", topic_id="t1")]
    items = build_items(CTX_0810, [topic_of(acts)], [SPEC], acts)
    assert types(items) == [ItemType.OPEN_QUESTION]


def test_assign_then_accept_merged_with_resolved_due():
    acts = [
        mk(1, Act.ASSIGN, "Lan", content="Dựng schema Postgres", assignee="Minh",
           due_text="thứ Sáu tuần sau"),
        mk(2, Act.ACCEPT_TASK, "Minh", content="ok em làm"),
    ]
    items = build_items(CTX_0810, [], [], acts)
    [ai] = [i for i in items if i.type == ItemType.ACTION_ITEM]
    assert len(items) == 1
    assert ai.owner == "Minh" and ai.due_date == date(2026, 10, 16)
    assert ai.content == "Dựng schema Postgres" and len(ai.evidence) == 2


def test_similar_assign_contents_grouped_and_distinct_kept_apart():
    acts = [
        mk(1, Act.ASSIGN, "Lan", content="Dựng schema Postgres", assignee="Minh"),
        mk(9, Act.ACCEPT_TASK, "Minh", content="dựng schema postgres"),
        mk(12, Act.ASSIGN, "Lan", content="Viết tài liệu API", assignee="Hoa"),
    ]
    items = build_items(CTX_0810, [], [], acts)
    assert [i.owner for i in items] == ["Minh", "Hoa"]


def test_accept_task_without_assignee_owner_is_speaker():
    acts = [mk(1, Act.ACCEPT_TASK, "Minh", content="Làm báo cáo")]
    [ai] = build_items(CTX_0810, [], [], acts)
    assert ai.owner == "Minh"


def test_blocker_request_feedback_knowledge_map_to_types():
    acts = [
        mk(1, Act.RAISE_BLOCKER, content="staging hỏng"),
        mk(2, Act.REQUEST, "Minh", content="cần quyền", assignee="Sales"),
        mk(3, Act.REQUEST, "Minh", content="cần thêm env"),
        mk(4, Act.FEEDBACK, content="UI khó dùng"),
        mk(5, Act.KNOWLEDGE, content="API giới hạn 100 rps"),
    ]
    items = build_items(CTX_0810, [], [], acts)
    assert types(items) == [
        ItemType.BLOCKER, ItemType.REQUEST, ItemType.REQUEST,
        ItemType.FEEDBACK, ItemType.KNOWLEDGE,
    ]
    assert items[1].requester == "Sales" and items[2].requester == "Minh"
    assert [i.id for i in items] == [f"m1-i00{n}" for n in range(1, 6)]


def test_unanswered_ask_makes_open_question():
    acts = [
        mk(1, Act.ASK, content="Ai lo deploy?", topic_hint="deploy"),
        mk(8, Act.KNOWLEDGE, content="x", topic_hint="deploy"),
    ]
    items = build_items(CTX_0810, [], [], acts)
    assert types(items) == [ItemType.OPEN_QUESTION, ItemType.KNOWLEDGE]
    assert items[0].content == "Ai lo deploy?" and items[0].status == ItemStatus.OPEN


def test_answered_ask_makes_no_item():
    acts = [
        mk(1, Act.ASK, content="Ai lo deploy?", topic_hint="deploy"),
        mk(3, Act.KNOWLEDGE, content="Minh lo deploy", topic_hint="deploy"),
    ]
    assert types(build_items(CTX_0810, [], [], acts)) == [ItemType.KNOWLEDGE]


def test_ask_inside_topic_makes_no_item():
    acts = [mk(1, Act.ASK, topic_id="t1", topic_hint="db"), mk(2, Act.DECIDE, "Lan",
            option="A", topic_id="t1")]
    items = build_items(CTX_0810, [topic_of(acts)], [SPEC], acts)
    assert types(items) == [ItemType.DECISION]


def test_topic_act_without_topic_id_is_ignored():
    acts = [mk(1, Act.SUPPORT, option="A"), mk(2, Act.DEFER)]
    assert build_items(CTX_0810, [], [], acts) == []


def test_unassigned_decide_makes_confirmation_question():
    acts = [
        mk(1, Act.DECIDE, "Lan", content="dùng Redis làm cache", quote="chốt Redis"),
        mk(2, Act.DECIDE, "Lan", quote="ok chốt vậy"),
        mk(3, Act.PROPOSE, option="A"),
    ]
    items = build_items(CTX_0810, [], [], acts)
    assert types(items) == [ItemType.OPEN_QUESTION, ItemType.OPEN_QUESTION]
    a, b = items
    assert a.content == "Cần xác nhận quyết định: dùng Redis làm cache"
    assert b.content == "Cần xác nhận quyết định: ok chốt vậy"
    assert a.status == ItemStatus.OPEN and a.topic_id is None
    assert a.flags == ["needs_confirmation"] and b.flags == ["needs_confirmation"]
    assert [e.utterance_id for e in a.evidence] == ["u1"]
    assert [e.quote for e in b.evidence] == ["ok chốt vậy"]


def test_hypothetical_dropped():
    acts = [mk(1, Act.HYPOTHETICAL, content="nếu có 10 người")]
    assert build_items(CTX_0810, [], [], acts) == []


def opt_decided_by(speaker: str, conf: float, object_after: bool = False) -> Option:
    d = mk(5, Act.DECIDE, speaker, option="A", confidence=conf)
    acts = [d]
    if object_after:
        acts.append(mk(6, Act.OBJECT, "Hoa", option="A"))
    return Option(label="A", state=OptState.DECIDED, decided_act=d, acts=acts)


def test_decision_confidence_penalties():
    assert decision_confidence(opt_decided_by("Minh", 1.0), CTX_MAKER_LAN) == 0.85
    assert decision_confidence(opt_decided_by("lan ", 1.0, object_after=True), CTX_MAKER_LAN) == 0.6
    assert decision_confidence(opt_decided_by("Lan", 0.9), CTX_MAKER_LAN) == 0.9


def test_decision_confidence_no_makers_no_penalty():
    ctx = CTX_0810.model_copy(update={"participants": [Participant(name="Minh")]})
    assert decision_confidence(opt_decided_by("Minh", 0.8), ctx) == 0.8


def test_ambiguous_decide_flags_needs_confirmation():
    acts = [
        mk(1, Act.PROPOSE, option="A", topic_id="t1"),
        mk(2, Act.PROPOSE, option="B", topic_id="t1"),
        mk(3, Act.DECIDE, "Lan", topic_id="t1"),
    ]
    t = topic_of(acts)
    assert t.ambiguous_decides
    [q] = build_items(CTX_0810, [t], [SPEC], acts)
    assert q.type == ItemType.OPEN_QUESTION and "needs_confirmation" in q.flags


def test_ambiguous_decide_with_decided_flags_decision():
    acts = [
        mk(1, Act.PROPOSE, option="A", topic_id="t1"),
        mk(2, Act.DECIDE, "Lan", option="A", topic_id="t1"),
    ]
    t = topic_of(acts)
    t.ambiguous_decides.append(mk(3, Act.DECIDE, "Hoa", topic_id="t1"))
    [d] = build_items(CTX_0810, [t], [SPEC], acts)
    assert d.type == ItemType.DECISION and "needs_confirmation" in d.flags


def test_needs_confirmation_topic_flags_open_question():
    acts = [mk(1, Act.PROPOSE, option="A", topic_id="t1")]
    t = topic_of(acts)
    t.needs_confirmation = True
    [q] = build_items(CTX_0810, [t], [SPEC], acts)
    assert "needs_confirmation" in q.flags


def test_items_ordered_by_first_evidence_and_inputs_not_mutated():
    acts = [
        mk(1, Act.KNOWLEDGE, content="k"),
        mk(2, Act.DECIDE, "Lan", option="A", topic_id="t1"),
        mk(3, Act.FEEDBACK, content="f", confidence=0.5),
    ]
    t = topic_of(acts)
    before = t.model_dump(), [a.model_dump() for a in acts]
    items = build_items(CTX_0810, [t], [SPEC], acts)
    assert types(items) == [ItemType.KNOWLEDGE, ItemType.DECISION, ItemType.FEEDBACK]
    assert items[2].confidence == 0.5
    assert (t.model_dump(), [a.model_dump() for a in acts]) == before


@pytest.mark.parametrize(
    ("question", "label", "expected"),
    [
        ("Dùng DB nào?", "Postgres", "Dùng DB nào? → Postgres"),
        ("Mời Bách vào vòng ba?", "Mời Bách vào vòng ba", "Mời Bách vào vòng ba"),
        ("  mời bách vào  vòng ba ? ", "Mời Bách vào vòng ba", "Mời Bách vào vòng ba"),
        ("", "Postgres", "Postgres"),
    ],
)
def test_decision_content_drops_yes_no_question(question: str, label: str, expected: str) -> None:
    assert decision_content(question, label) == expected
