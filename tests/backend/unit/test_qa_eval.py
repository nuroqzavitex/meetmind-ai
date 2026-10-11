import json
from datetime import date
from pathlib import Path

import pytest
from evals.metrics.qa import (
    QAQuestion,
    citation_correct,
    latest_correct,
    load_qa_thresholds,
    refusal_correct,
    score,
)
from evals.runners.run_qa import main

from app.ai.agents.qa import REFUSAL
from app.schemas.qa import Citation, QAResponse

EVALS = Path(__file__).resolve().parents[3] / "evals"
QUESTIONS = EVALS / "datasets" / "qa" / "questions.json"


def cite(quote: str) -> Citation:
    return Citation(
        ref=1, meeting_id="m", title="t", date=date(2026, 10, 5), ts="00:02:05",
        speaker="Hạnh", quote=quote, utterance_id="u0005",
    )


def resp(answer: str, *quotes: str) -> QAResponse:
    return QAResponse(answer=answer, citations=[cite(q) for q in quotes])


def q(kind: str = "answer", **kw) -> QAQuestion:
    base = {"id": "q", "question": "?", "kind": kind, "meetings": ["a_to_b"]}
    base.update(kw)
    return QAQuestion(**base)


def test_citation_correct_casefold_any_match():
    qq = q(expect_quote_contains=["chốt amazon ses"])
    assert citation_correct(resp("SES [1]", "Ok, vậy bỏ SendGrid, mình chốt Amazon SES."), qq)
    assert not citation_correct(resp("SES [1]", "Em đề xuất dùng SendGrid"), qq)
    assert not citation_correct(resp(REFUSAL), qq)


def test_latest_correct_needs_option_and_citation():
    qq = q("latest", expect_answer_contains=["Amazon SES"])
    assert latest_correct(resp("Đã chốt amazon ses [1]", "x"), qq)
    assert not latest_correct(resp("Đã chốt SendGrid [1]", "x"), qq)
    assert not latest_correct(resp("Đã chốt Amazon SES"), qq)


def test_refusal_correct():
    assert refusal_correct(resp(REFUSAL))
    assert not refusal_correct(resp(REFUSAL, "x"))
    assert not refusal_correct(resp("Có chứ [1]", "x"))


def test_score_per_kind():
    results = [
        (q("answer", expect_quote_contains=["ses"]), resp("a [1]", "chốt SES")),
        (q("answer", expect_quote_contains=["ses"]), resp("a [1]", "khác")),
        (q("latest", expect_answer_contains=["ses"], expect_quote_contains=["ses"]),
         resp("SES [1]", "chốt SES")),
        (q("refusal"), resp(REFUSAL)),
        (q("refusal"), resp("bịa [1]", "x")),
    ]
    s = score(results)
    assert s["qa_citation_accuracy"] == pytest.approx(2 / 3)
    assert s["qa_latest_state_accuracy"] == 1.0
    assert s["qa_refusal_accuracy"] == 0.5
    assert score(results[3:4]) == {"qa_refusal_accuracy": 1.0}


def test_thresholds():
    assert load_qa_thresholds() == {
        "qa_citation_accuracy": 0.85,
        "qa_latest_state_accuracy": 1.0,
        "qa_refusal_accuracy": 1.0,
    }


def test_questions_dataset_valid():
    qs = [QAQuestion.model_validate(x) for x in json.loads(QUESTIONS.read_text(encoding="utf-8"))]
    assert len({x.id for x in qs}) == len(qs)
    kinds = [x.kind for x in qs]
    assert kinds.count("latest") >= 4 and kinds.count("refusal") >= 4
    assert kinds.count("answer") >= 4
    goldens = {p.stem for p in (EVALS / "golden").glob("*.json")}
    for x in qs:
        assert x.meetings and set(x.meetings) <= goldens, x.id
        if x.kind != "refusal":
            assert x.expect_quote_contains, x.id
        if x.kind == "latest":
            assert x.expect_answer_contains, x.id


def test_questions_expectations_are_in_transcripts():
    qs = [QAQuestion.model_validate(x) for x in json.loads(QUESTIONS.read_text(encoding="utf-8"))]
    for x in qs:
        if x.kind == "refusal":
            continue
        text = "\n".join(
            (EVALS / "datasets" / d / f"{m}.txt").read_text(encoding="utf-8")
            for m in x.meetings
            for d in ("synthetic", "transcripts")
            if (EVALS / "datasets" / d / f"{m}.txt").exists()
        ).casefold()
        assert any(s.casefold() in text for s in x.expect_quote_contains), x.id


def test_runner_exits_2_without_api_key(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["--only", "qa_latest_a_to_b"]) == 2
    err = capsys.readouterr().err
    assert "ANTHROPIC_API_KEY" in err and len(err.strip().splitlines()) == 1


def test_runner_exits_2_when_postgres_unreachable(monkeypatch, capsys):
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://app:app@127.0.0.1:1/meeting_test")
    called = []

    def factory(settings):
        called.append(1)
        raise AssertionError("LLM must not be built")

    assert main([], llm_factory=factory) == 2
    err = capsys.readouterr().err
    assert len(err.strip().splitlines()) == 1 and "Postgres" in err
    assert not called


def test_runner_refuses_non_test_database(monkeypatch, capsys):
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://app:app@127.0.0.1:1/meeting")
    assert main([], llm_factory=lambda s: None) == 2  # type: ignore[arg-type,return-value]
    err = capsys.readouterr().err
    assert "_test" in err and len(err.strip().splitlines()) == 1


def test_citation_correct_window_path():
    qq = q(expect_quote_contains=["chốt amazon ses"])
    r = resp("SES [1]", "Hôm nay mình chọn dịch vụ gửi email")  # chunk first line only
    assert not citation_correct(r, qq)
    seen = []

    def window(meeting_id: str, utterance_id: str) -> str:
        seen.append((meeting_id, utterance_id))
        return "Hạnh: Ok, vậy bỏ SendGrid, mình chốt Amazon SES."

    assert citation_correct(r, qq, window)
    assert seen == [("m", "u0005")]
    assert not citation_correct(r, q(expect_quote_contains=["kubernetes"]), window)
    assert score([(qq, r)], window) == {"qa_citation_accuracy": 1.0}
