"""Per-meeting scoring and aggregation against spec 13.2 thresholds."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from app.ai.agents.check_quotes import quote_matches
from app.ai.domain.enums import ItemStatus, ItemType
from app.ai.domain.models import MeetingItem, Utterance
from app.ai.domain.names import norm_name
from app.ai.pipeline import AnalysisResult
from evals.metrics.matching import (
    Golden,
    GoldTopic,
    contains_keyword,
    decision_label,
    match_items,
)

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"


class MeetingScore(BaseModel):
    per_type: dict[str, tuple[int, int, int]]  # (tp, n_pred, n_gold)
    final_decision_correct: int
    final_decision_total: int
    owner_due_correct: int
    owner_due_total: int
    evidence_ok: int
    evidence_total: int
    trap_correct: bool | None = None


def load_thresholds(path: Path = CONFIG_PATH) -> dict[str, float]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {k: float(v) for k, v in data["thresholds"].items()}


def _topic_correct(topic: GoldTopic, items: list[MeetingItem]) -> bool:
    decisions = [
        i for i in items
        if i.type == ItemType.DECISION and contains_keyword(i.content, topic.match)
    ]
    if topic.final_option is None:
        return not decisions
    finals = [d for d in decisions if d.status == ItemStatus.FINAL]
    return len(finals) == 1 and contains_keyword(
        decision_label(finals[0].content), topic.final_match
    )


def score_meeting(
    res: AnalysisResult, golden: Golden, transcript_utts: list[Utterance]
) -> MeetingScore:
    pairs = match_items(res.items, golden.items)
    per_type: dict[str, tuple[int, int, int]] = {}
    for t in ItemType:
        n_pred = sum(1 for i in res.items if i.type == t)
        n_gold = sum(1 for g in golden.items if g.type == t)
        tp = sum(1 for _, gi in pairs if golden.items[gi].type == t)
        per_type[t.value] = (tp, n_pred, n_gold)

    od_total = od_ok = 0
    for pi, gi in pairs:
        g = golden.items[gi]
        if g.type != ItemType.ACTION_ITEM:
            continue
        p = res.items[pi]
        od_total += 1
        owner_ok = (norm_name(p.owner) if p.owner else None) == (
            norm_name(g.owner) if g.owner else None
        )
        if owner_ok and p.due_date == g.due_date:
            od_ok += 1

    by_id = {u.id: u for u in transcript_utts}
    ev_total = ev_ok = 0
    for it in res.items:
        for ev in it.evidence:
            ev_total += 1
            u = by_id.get(ev.utterance_id)
            if u is not None and quote_matches(ev.quote, u.text):
                ev_ok += 1

    correct = [_topic_correct(t, res.items) for t in golden.topics]
    return MeetingScore(
        per_type=per_type,
        final_decision_correct=sum(correct), final_decision_total=len(correct),
        owner_due_correct=od_ok, owner_due_total=od_total,
        evidence_ok=ev_ok, evidence_total=ev_total,
        trap_correct=all(correct) if golden.kind == "trap" else None,
    )


def _ratio(num: int, den: int, name: str, notes: list[str]) -> float:
    if den == 0:
        notes.append(f"{name}: zero denominator, scored 1.0")
        return 1.0
    return num / den


def aggregate(
    scores: list[MeetingScore], thresholds: dict[str, float] | None = None
) -> dict[str, Any]:
    th = thresholds if thresholds is not None else load_thresholds()
    notes: list[str] = []
    tp = sum(v[0] for s in scores for v in s.per_type.values())
    n_pred = sum(v[1] for s in scores for v in s.per_type.values())
    n_gold = sum(v[2] for s in scores for v in s.per_type.values())
    traps = [s.trap_correct for s in scores if s.trap_correct is not None]
    out: dict[str, Any] = {
        "precision": _ratio(tp, n_pred, "precision", notes),
        "recall": _ratio(tp, n_gold, "recall", notes),
        "final_decision_accuracy": _ratio(
            sum(s.final_decision_correct for s in scores),
            sum(s.final_decision_total for s in scores), "final_decision_accuracy", notes),
        "owner_due_accuracy": _ratio(
            sum(s.owner_due_correct for s in scores),
            sum(s.owner_due_total for s in scores), "owner_due_accuracy", notes),
        "evidence_faithfulness": _ratio(
            sum(s.evidence_ok for s in scores),
            sum(s.evidence_total for s in scores), "evidence_faithfulness", notes),
        "trap_accuracy": _ratio(sum(traps), len(traps), "trap_accuracy", notes),
    }
    out["thresholds"] = th
    out["notes"] = notes
    out["pass"] = all(out[k] >= v for k, v in th.items())
    return out
