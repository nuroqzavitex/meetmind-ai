from datetime import date
from typing import Any

import pytest
from tests.backend.pipeline_helpers import CTX_PAYMENT, PAYMENT, fake_from_fixtures, fx

from app.ai.config import AISettings
from app.ai.domain.enums import ItemType
from app.ai.errors import AnalysisError, LLMError, TranscriptParseError
from app.ai.llm.fake import FakeLLM
from app.ai.pipeline import analyze_transcript

CTX = CTX_PAYMENT.model_copy(update={"participants": []})


def make_txt(n: int) -> bytes:
    return "\n".join(
        f"[00:{i // 60:02d}:{i % 60:02d}] Lan: câu số {i}" for i in range(n)
    ).encode()


def bad_acts() -> dict[str, Any]:
    acts = fx("extract.json")["acts"]
    return {"acts": [{**a, "quote": "hoàn toàn bịa đặt không có thật xyz"} for a in acts]}


async def test_payment_v2_end_to_end_with_fake_llm():
    res = await analyze_transcript(
        ctx=CTX_PAYMENT, filename="payment_v2.txt", data=PAYMENT,
        llm=fake_from_fixtures(), settings=AISettings(),
    )
    dec = [i for i in res.items if i.type == ItemType.DECISION]
    assert len(dec) == 1 and "Postgres" in dec[0].content
    assert dec[0].supersedes == ["MongoDB"] and dec[0].owner == "Lan"
    ai = [i for i in res.items if i.type == ItemType.ACTION_ITEM]
    assert any(i.owner == "Minh" and i.due_date == date(2026, 10, 16) for i in ai)
    assert any(i.owner == "Hoa" for i in ai) and any(i.owner == "Lan" for i in ai)
    assert not any("hoàn tiền" in e.quote for i in res.items for e in i.evidence)
    assert {i.type for i in res.items} >= {
        ItemType.BLOCKER, ItemType.REQUEST, ItemType.OPEN_QUESTION,
        ItemType.KNOWLEDGE, ItemType.FEEDBACK,
    }
    assert len(res.utterances) == 16 and res.specs and res.topics


async def test_retry_once_when_quotes_bad():
    llm = FakeLLM({
        "extract": [bad_acts(), fx("extract.json")], "topics": [fx("topics.json")],
    })
    res = await analyze_transcript(
        ctx=CTX_PAYMENT, filename="p.txt", data=PAYMENT, llm=llm, settings=AISettings()
    )
    assert len([c for c in llm.calls if c[0] == "extract"]) == 2
    assert any(i.type == ItemType.DECISION for i in res.items)


async def test_retry_only_once_even_if_still_bad():
    llm = FakeLLM({"extract": [bad_acts(), bad_acts(), bad_acts()]})
    res = await analyze_transcript(
        ctx=CTX_PAYMENT, filename="p.txt", data=PAYMENT, llm=llm, settings=AISettings()
    )
    assert len([c for c in llm.calls if c[0] == "extract"]) == 2
    assert res.acts == [] and res.items == []


async def test_no_decisions_meeting_returns_items_without_error():
    fb = {"acts": [{
        "utterance_id": "u0015", "act": "feedback", "confidence": 0.9,
        "quote": "Tài liệu API đợt này viết rõ hơn hẳn", "content": "Tài liệu API rõ hơn",
    }]}
    res = await analyze_transcript(
        ctx=CTX_PAYMENT, filename="p.txt", data=PAYMENT,
        llm=FakeLLM({"extract": [fb]}), settings=AISettings(),
    )
    assert [i.type for i in res.items] == [ItemType.FEEDBACK]
    assert res.topics == [] and res.specs == []


async def test_long_transcript_respects_concurrency():
    llm = FakeLLM({"extract": [{"acts": []}] * 11})
    await analyze_transcript(
        ctx=CTX, filename="long.txt", data=make_txt(380), llm=llm,
        settings=AISettings(max_concurrency=4),
    )
    assert len([c for c in llm.calls if c[0] == "extract"]) == 11
    assert llm.max_in_flight <= 4


async def test_llm_error_wrapped_with_step():
    def boom(_: str) -> Any:
        raise LLMError("down")

    llm = FakeLLM({"extract": [fx("extract.json")], "topics": [boom]})
    with pytest.raises(AnalysisError) as ei:
        await analyze_transcript(
            ctx=CTX_PAYMENT, filename="p.txt", data=PAYMENT, llm=llm, settings=AISettings()
        )
    assert ei.value.step == "topics" and isinstance(ei.value.__cause__, LLMError)


async def test_unexpected_node_error_wrapped_with_step():
    def boom(_: str) -> Any:
        raise RuntimeError("bug")

    llm = FakeLLM({"extract": [fx("extract.json")], "topics": [boom]})
    with pytest.raises(AnalysisError) as ei:
        await analyze_transcript(
            ctx=CTX_PAYMENT, filename="p.txt", data=PAYMENT, llm=llm, settings=AISettings()
        )
    assert ei.value.step == "topics" and isinstance(ei.value.__cause__, RuntimeError)


async def test_parse_error_propagates_unchanged():
    with pytest.raises(TranscriptParseError):
        await analyze_transcript(
            ctx=CTX, filename="x.pdf", data=b"x", llm=FakeLLM({}), settings=AISettings()
        )


async def test_progress_reported_in_order():
    calls: list[tuple[str, float]] = []

    async def on_progress(step: str, p: float) -> None:
        calls.append((step, p))

    await analyze_transcript(
        ctx=CTX_PAYMENT, filename="p.txt", data=PAYMENT, llm=fake_from_fixtures(),
        settings=AISettings(), on_progress=on_progress,
    )
    steps = [s for s, _ in calls]
    assert steps == [
        "normalize", "extract", "check_quotes", "topics",
        "state_machine", "arbitrate", "build_items", "validate", "done",
    ]
    values = [p for _, p in calls]
    assert values == sorted(values) and calls[-1] == ("done", 1.0)
