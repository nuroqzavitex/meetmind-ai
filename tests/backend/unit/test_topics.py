from datetime import date

from app.ai.agents.topics import assign_topics
from app.ai.domain.enums import Act
from app.ai.domain.models import DialogueAct, MeetingContext
from app.ai.llm import FakeLLM

CTX = MeetingContext(meeting_id="m1", title="Chốt CSDL", meeting_date=date(2026, 10, 10))


def _act(i: str, act: Act, seq: int, option: str | None = None) -> DialogueAct:
    return DialogueAct(
        id=i, utterance_id=f"u{seq:04d}", seq=seq, speaker="Minh", start=float(seq),
        act=act, quote="q", option=option,
    )


A1_PROPOSE = _act("a1", Act.PROPOSE, 1, "Mongo")
A2_SUPPORT = _act("a2", Act.SUPPORT, 2)
A3_ASSIGN = _act("a3", Act.ASSIGN, 3)


async def test_assign_topics_applies_aliases_and_ignores_unknown():
    llm = FakeLLM({"topics": [{"topics": [{"topic_id": "t1", "question": "CSDL nào?"}],
        "aliases": [{"alias": "Mongo", "canonical": "MongoDB"}],
        "assignments": [{"act_id": "a1", "topic_id": "t1", "option": "Mongo"},
                        {"act_id": "zzz", "topic_id": "t1", "option": "X"},
                        {"act_id": "a2", "topic_id": "t9", "option": "Y"}]}]})
    specs, out = await assign_topics(llm, CTX, [A1_PROPOSE, A2_SUPPORT, A3_ASSIGN], "v1")
    by = {a.id: a for a in out}
    assert [s.topic_id for s in specs] == ["t1"]
    assert by["a1"].topic_id == "t1" and by["a1"].option == "MongoDB"
    assert by["a2"].topic_id is None and by["a3"] == A3_ASSIGN
    assert [a.id for a in out] == ["a1", "a2", "a3"]
    assert A1_PROPOSE.topic_id is None and A1_PROPOSE.option == "Mongo"
    user = llm.calls[0][1]
    assert "a1 |" in user and "a3" not in user


async def test_no_topic_acts_skips_llm():
    llm = FakeLLM({})
    assert (await assign_topics(llm, CTX, [A3_ASSIGN], "v1"))[0] == [] and llm.calls == []
