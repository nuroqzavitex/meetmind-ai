import json
from datetime import date
from pathlib import Path

import pytest
from evals.metrics.matching import Golden, GoldItem, GoldTopic, match_items, strip_accents
from evals.metrics.scores import MeetingScore, aggregate, load_thresholds, score_meeting
from evals.runners.run_pipeline import main

from app.ai.domain.enums import ItemStatus, ItemType
from app.ai.domain.models import Evidence, MeetingContext, MeetingItem, Utterance
from app.ai.llm.fake import FakeLLM
from app.ai.pipeline import AnalysisResult

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "llm" / "payment_v2"
CTX = MeetingContext(meeting_id="m", title="t", meeting_date=date(2026, 10, 8))


def item(type_: ItemType, content: str, *, status: ItemStatus = ItemStatus.FINAL,
         owner: str | None = None, due: date | None = None,
         quote: str = "chốt Postgres", uid: str = "u0001") -> MeetingItem:
    return MeetingItem(
        id="i", meeting_id="m", type=type_, content=content, status=status, owner=owner,
        due_date=due, evidence=[Evidence(utterance_id=uid, speaker="Lan", ts="00:00:01",
                                         quote=quote)],
    )


UTTS = [Utterance(id="u0001", seq=0, speaker="Lan", start=1.0, text="Vậy mình chốt Postgres nhé")]


def golden(kind: str = "realistic", final: str | None = "PostgreSQL") -> Golden:
    return Golden(
        context=CTX, transcript="x", kind=kind,  # type: ignore[arg-type]
        topics=[GoldTopic(question="db", final_option=final, match=["postgres"],
                          final_match=["postgres"] if final else [])],
        items=[
            GoldItem(type=ItemType.DECISION, content="Dùng PostgreSQL", match=["postgres"]),
            GoldItem(type=ItemType.ACTION_ITEM, content="Dựng schema", match=["schema"],
                     owner="Minh", due_date=date(2026, 10, 16)),
        ],
    )


def result(items: list[MeetingItem]) -> AnalysisResult:
    return AnalysisResult(utterances=UTTS, acts=[], topics=[], specs=[], items=items)


def test_strip_accents():
    assert strip_accents("Hoá đơn") == "hoa don"
    assert strip_accents("ĐỒNG Ý") == "dong y"


def test_match_items_by_type_and_keyword():
    pred = [
        item(ItemType.BLOCKER, "Postgres hỏng"),
        item(ItemType.DECISION, "Chốt dùng Postgres"),
    ]
    gold = golden().items[:1]
    assert match_items(pred, gold) == [(1, 0)]


def test_match_items_each_used_once_best_first():
    pred = [item(ItemType.DECISION, "Postgres"), item(ItemType.DECISION, "Dùng PostgreSQL")]
    gold = golden().items[:1]
    assert match_items(pred, gold) == [(1, 0)]


def test_score_meeting_perfect():
    res = result([
        item(ItemType.DECISION, "Chốt dùng Postgres"),
        item(ItemType.ACTION_ITEM, "Dựng schema", owner="minh", due=date(2026, 10, 16)),
    ])
    s = score_meeting(res, golden(), UTTS)
    assert s.per_type["decision"] == (1, 1, 1)
    assert (s.final_decision_correct, s.final_decision_total) == (1, 1)
    assert (s.owner_due_correct, s.owner_due_total) == (1, 1)
    assert (s.evidence_ok, s.evidence_total) == (2, 2)
    assert s.trap_correct is None


def test_owner_due_wrong_and_bad_evidence():
    res = result([
        item(ItemType.DECISION, "Chốt Postgres", quote="bịa đặt hoàn toàn"),
        item(ItemType.ACTION_ITEM, "Dựng schema", owner="Minh", due=None),
    ])
    s = score_meeting(res, golden(), UTTS)
    assert s.owner_due_correct == 0 and s.owner_due_total == 1
    assert s.evidence_ok == 1 and s.evidence_total == 2


def test_evidence_check_is_casefolded_like_check_quotes():
    res = result([item(ItemType.DECISION, "Chốt Postgres", quote="VẬY MÌNH CHỐT POSTGRES")])
    s = score_meeting(res, golden(), UTTS)
    assert (s.evidence_ok, s.evidence_total) == (1, 1)


def test_final_decision_needs_exactly_one_final():
    two = result([item(ItemType.DECISION, "Postgres a"), item(ItemType.DECISION, "Postgres b")])
    assert score_meeting(two, golden(), UTTS).final_decision_correct == 0
    sup = result([item(ItemType.DECISION, "Postgres", status=ItemStatus.SUPERSEDED)])
    assert score_meeting(sup, golden(), UTTS).final_decision_correct == 0


def test_final_option_null_requires_no_decision():
    g = golden(final=None)
    assert score_meeting(result([]), g, UTTS).final_decision_correct == 1
    assert score_meeting(
        result([item(ItemType.DECISION, "Postgres")]), g, UTTS
    ).final_decision_correct == 0


def test_trap_incorrect_when_any_topic_wrong():
    g = golden(kind="trap")
    assert score_meeting(result([item(ItemType.DECISION, "Postgres")]), g, UTTS).trap_correct is True
    assert score_meeting(result([]), g, UTTS).trap_correct is False


EMAIL_Q = "Dịch vụ gửi email thông báo"


def email_golden() -> Golden:
    return Golden(
        context=CTX, transcript="x", kind="trap",
        topics=[GoldTopic(question=EMAIL_Q, final_option="Amazon SES",
                          match=["email", "sendgrid", "amazon"], final_match=["ses"])],
        items=[GoldItem(type=ItemType.DECISION, content=f"{EMAIL_Q} → Amazon SES",
                        match=["amazon", "ses"])],
    )


def test_superseded_option_decision_makes_topic_incorrect():
    wrong = score_meeting(result([item(ItemType.DECISION, f"{EMAIL_Q} → SendGrid")]),
                          email_golden(), UTTS)
    assert wrong.final_decision_correct == 0 and wrong.trap_correct is False
    assert wrong.per_type["decision"] == (0, 1, 1)
    right = score_meeting(result([item(ItemType.DECISION, f"{EMAIL_Q} → Amazon SES")]),
                          email_golden(), UTTS)
    assert right.final_decision_correct == 1 and right.trap_correct is True
    assert right.per_type["decision"] == (1, 1, 1)


def test_option_named_in_question_does_not_count_as_final_option():
    pred = item(ItemType.DECISION, "Chọn Amazon SES hay SendGrid để gửi email? → SendGrid")
    s = score_meeting(result([pred]), email_golden(), UTTS)
    assert s.final_decision_correct == 0 and s.per_type["decision"][0] == 0


def test_correct_and_superseded_final_decisions_both_present_is_incorrect():
    both = result([item(ItemType.DECISION, f"{EMAIL_Q} → Amazon SES"),
                   item(ItemType.DECISION, f"{EMAIL_Q} → SendGrid")])
    assert score_meeting(both, email_golden(), UTTS).final_decision_correct == 0


def test_gold_topic_requires_final_match_when_final_option_set():
    with pytest.raises(ValueError, match="final_match"):
        GoldTopic(question="q", final_option="A", match=["abcd"])
    assert GoldTopic(question="q", final_option=None, match=["abcd"]).final_match == []


def perfect_score() -> MeetingScore:
    return MeetingScore(
        per_type={"decision": (10, 10, 10)}, final_decision_correct=1, final_decision_total=1,
        owner_due_correct=2, owner_due_total=2, evidence_ok=5, evidence_total=5, trap_correct=None,
    )


def half_recall_score() -> MeetingScore:
    return perfect_score().model_copy(update={"per_type": {"decision": (5, 5, 10)}})


def test_aggregate_thresholds():
    agg = aggregate([perfect_score(), half_recall_score()])
    assert agg["recall"] == pytest.approx(0.75) and agg["pass"] is True
    assert agg["precision"] == pytest.approx(1.0)


def test_aggregate_fails_below_threshold_and_empty_denominators():
    bad = perfect_score().model_copy(update={"evidence_ok": 4})
    assert aggregate([bad])["pass"] is False
    agg = aggregate([perfect_score()])
    assert agg["trap_accuracy"] == 1.0 and agg["notes"]


def test_thresholds_loaded_from_config():
    t = load_thresholds()
    assert t["precision"] == 0.85 and t["recall"] == 0.75 and t["evidence_faithfulness"] == 1.0


def test_runner_exits_2_without_api_key(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["--only", "payment_v2"]) == 2
    err = capsys.readouterr().err
    assert "ANTHROPIC_API_KEY" in err and len(err.strip().splitlines()) == 1


def test_runner_scores_with_fake_llm(tmp_path, capsys):
    fx = lambda n: json.loads((FIX / n).read_text(encoding="utf-8"))
    llm = FakeLLM({"extract": [fx("extract.json")], "topics": [fx("topics.json")]})
    code = main(["--only", "payment_v2", "--report-dir", str(tmp_path)], llm_factory=lambda _: llm)
    assert code in (0, 1)
    out = capsys.readouterr().out
    assert "precision" in out and "recall" in out
    reports = list(tmp_path.glob("*.json"))
    assert len(reports) == 1
    rep = json.loads(reports[0].read_text(encoding="utf-8"))
    assert rep["meetings"]["payment_v2"]["items"] and "aggregate" in rep
