from datetime import date

from app.ai.agents.extract import dedupe_acts, extract_chunk, render_chunk
from app.ai.agents.normalize import Chunk
from app.ai.domain.enums import Act
from app.ai.domain.models import DialogueAct, MeetingContext, Participant, Utterance
from app.ai.llm import FakeLLM

CTX = MeetingContext(
    meeting_id="m1",
    title="Chốt CSDL",
    meeting_date=date(2026, 10, 10),
    participants=[Participant(name="Lan", role="PM", is_decision_maker=True), Participant(name="Minh", role="Dev")],
    glossary=["MongoDB"],
)
CHUNK = Chunk(
    index=0,
    utterances=[
        Utterance(id="u0000", seq=0, speaker="Lan", start=5.0, text="Hôm nay mình chốt CSDL cho module thanh toán."),
        Utterance(id="u0001", seq=1, speaker="Minh", start=20.0, text="Em đề xuất dùng MongoDB cho nhanh, schema linh hoạt."),
    ],
)


def _act(uid: str, act: Act, option: str | None, conf: float, seq: int = 1, start: float = 20.0) -> DialogueAct:
    return DialogueAct(
        id=f"a{seq:04d}_0", utterance_id=uid, seq=seq, speaker="Minh", start=start,
        act=act, quote="q", option=option, confidence=conf,
    )


def test_render_chunk():
    assert render_chunk(CHUNK).splitlines()[1].startswith("u0001 [00:00:20] Minh: Em đề xuất")


async def test_extract_fills_fields_and_drops_unknown_utterance():
    llm = FakeLLM({"extract": [{"acts": [
        {"utterance_id": "u0001", "act": "propose", "quote": "dùng MongoDB", "option": "MongoDB", "confidence": 0.9},
        {"utterance_id": "u9999", "act": "decide", "quote": "x", "confidence": 0.9}]}]})
    acts = await extract_chunk(llm, CTX, CHUNK, "v1")
    assert len(acts) == 1 and acts[0].speaker == "Minh" and acts[0].start == 20 and acts[0].seq == 1
    assert acts[0].id == "a0001_0"
    assert "u0001 [00:00:20] Minh:" in llm.calls[0][1]


def test_dedupe_overlap_keeps_higher_confidence():
    out = dedupe_acts([_act("u0001", Act.PROPOSE, "Mongo", 0.6), _act("u0001", Act.PROPOSE, "Mongo", 0.9)])
    assert len(out) == 1 and out[0].confidence == 0.9


def test_dedupe_sorted_and_distinct_keys():
    a = _act("u0002", Act.DECIDE, "Mongo", 0.8, seq=2, start=30.0)
    b = _act("u0001", Act.PROPOSE, "Mongo", 0.8)
    assert dedupe_acts([a, b]) == [b, a]


def test_dedupe_reassigns_unique_ids_across_overlapping_chunks():
    # chunk A returned [propose, support] -> a0001_0, a0001_1; chunk B returned only [support] -> a0001_0
    propose = _act("u0001", Act.PROPOSE, "Mongo", 0.8)
    support = _act("u0001", Act.SUPPORT, "Mongo", 0.8)
    assert propose.id == support.id == "a0001_0"
    out = dedupe_acts([propose, support])
    assert sorted(a.id for a in out) == ["a0001_0", "a0001_1"]
    assert propose.id == support.id == "a0001_0"  # inputs not mutated


def test_dedupe_confidence_tie_keeps_first():
    first = _act("u0001", Act.PROPOSE, "Mongo", 0.8)
    first.content = "first"
    second = _act("u0001", Act.PROPOSE, "Mongo", 0.8)
    second.content = "second"
    assert dedupe_acts([first, second])[0].content == "first"
