"""Re-score a saved run_pipeline report with the commitment guard applied to its items.

The guard is deterministic code after the LLM steps, so applying it to the items of a run made
without it isolates its effect from LLM run-to-run variance (same LLM output, guard on vs off).

    cd backend && PYTHONPATH=.. uv run python -m evals.runners.replay_guard <report.json>
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.ai.domain.commitment_guard import guard_items
from app.ai.domain.models import MeetingItem
from app.ai.parsing import parse_transcript
from app.ai.pipeline import AnalysisResult
from evals.metrics.matching import Golden
from evals.metrics.scores import MeetingScore, aggregate, load_thresholds, score_meeting

EVALS_DIR = Path(__file__).resolve().parents[1]


def replay(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Aggregates of the report as saved and with the guard applied, scored the same way."""
    before: list[MeetingScore] = []
    after: list[MeetingScore] = []
    for name, meeting in report["meetings"].items():
        golden = Golden.model_validate_json(
            (EVALS_DIR / "golden" / f"{name}.json").read_text(encoding="utf-8")
        )
        path = EVALS_DIR / golden.transcript
        utts = parse_transcript(path.name, path.read_bytes())
        items = [MeetingItem.model_validate(i) for i in meeting["items"]]
        for chosen, out in ((items, before), (guard_items(items, utts), after)):
            res = AnalysisResult(utterances=utts, acts=[], topics=[], specs=[], items=chosen)
            out.append(score_meeting(res, golden, utts))
    return aggregate(before), aggregate(after)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="replay_guard")
    ap.add_argument("reports", nargs="+", type=Path)
    args = ap.parse_args(argv)
    th = load_thresholds()
    for path in args.reports:
        before, after = replay(json.loads(path.read_text(encoding="utf-8")))
        print(f"{path.name}\n{'metric':<26}{'saved':>8}{'+guard':>8}")
        for k in th:
            print(f"{k:<26}{before[k]:>8.3f}{after[k]:>8.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
