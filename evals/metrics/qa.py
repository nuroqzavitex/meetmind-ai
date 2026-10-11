"""Metrics for the QA eval: citation accuracy, latest-state accuracy, refusal accuracy."""

from collections.abc import Callable
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

from app.ai.agents.qa import REFUSAL
from app.schemas.qa import QAResponse

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"


class QAQuestion(BaseModel):
    id: str
    question: str
    kind: Literal["answer", "latest", "refusal"]
    meetings: list[str]  # golden names (stems of evals/golden/*.json)
    expect_quote_contains: list[str] = []
    expect_answer_contains: list[str] = []
    forbid_answer_contains: list[str] = []  # documentation only, not checked textually


def load_qa_thresholds(path: Path = CONFIG_PATH) -> dict[str, float]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {k: float(v) for k, v in data["qa_thresholds"].items()}


def _contains_any(text: str, needles: list[str]) -> bool:
    folded = text.casefold()
    return any(n.casefold() in folded for n in needles)


Window = Callable[[str, str], str]  # (meeting_id, utterance_id) -> transcript window text


def citation_correct(resp: QAResponse, q: QAQuestion, window: Window | None = None) -> bool:
    """Any citation whose quote (or, with `window`, transcript window from its utterance) matches."""
    for c in resp.citations:
        text = c.quote if window is None else f"{c.quote}\n{window(c.meeting_id, c.utterance_id)}"
        if _contains_any(text, q.expect_quote_contains):
            return True
    return False


def latest_correct(resp: QAResponse, q: QAQuestion) -> bool:
    return bool(resp.citations) and _contains_any(resp.answer, q.expect_answer_contains)


def refusal_correct(resp: QAResponse) -> bool:
    return resp.answer == REFUSAL and not resp.citations


def score(
    results: list[tuple[QAQuestion, QAResponse]], window: Window | None = None
) -> dict[str, float]:
    """Accuracy per metric; a metric is omitted when no question of its kind was run."""
    cited = [(q, r) for q, r in results if q.kind in ("answer", "latest")]
    latest = [(q, r) for q, r in results if q.kind == "latest"]
    refusals = [r for q, r in results if q.kind == "refusal"]
    out: dict[str, float] = {}
    if cited:
        out["qa_citation_accuracy"] = sum(citation_correct(r, q, window) for q, r in cited) / len(cited)
    if latest:
        out["qa_latest_state_accuracy"] = sum(latest_correct(r, q) for q, r in latest) / len(latest)
    if refusals:
        out["qa_refusal_accuracy"] = sum(refusal_correct(r) for r in refusals) / len(refusals)
    return out
