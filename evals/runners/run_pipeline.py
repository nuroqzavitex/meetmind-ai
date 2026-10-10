"""CLI: run the real pipeline over evals/golden/*.json and score it."""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ai.config import AISettings
from app.ai.llm.client import AnthropicLLM, LLMClient
from app.ai.pipeline import analyze_transcript
from evals.metrics.matching import Golden
from evals.metrics.scores import MeetingScore, aggregate, load_thresholds, score_meeting

EVALS_DIR = Path(__file__).resolve().parents[1]
LLMFactory = Callable[[AISettings], LLMClient]


def _anthropic(settings: AISettings) -> LLMClient:
    return AnthropicLLM(settings)


def _load_goldens(only: str | None, kind: str | None) -> dict[str, Golden]:
    out: dict[str, Golden] = {}
    for p in sorted((EVALS_DIR / "golden").glob("*.json")):
        if only and p.stem != only:
            continue
        g = Golden.model_validate_json(p.read_text(encoding="utf-8"))
        if kind and g.kind != kind:
            continue
        out[p.stem] = g
    return out


async def _run(
    goldens: dict[str, Golden], llm: LLMClient, settings: AISettings
) -> tuple[dict[str, MeetingScore], dict[str, Any]]:
    scores: dict[str, MeetingScore] = {}
    details: dict[str, Any] = {}
    for name, g in goldens.items():
        data = (EVALS_DIR / g.transcript).read_bytes()
        res = await analyze_transcript(
            ctx=g.context, filename=Path(g.transcript).name, data=data, llm=llm,
            settings=settings,
        )
        scores[name] = score_meeting(res, g, res.utterances)
        details[name] = {
            "score": scores[name].model_dump(mode="json"),
            "items": [i.model_dump(mode="json") for i in res.items],
        }
    return scores, details


def main(argv: list[str] | None = None, llm_factory: LLMFactory | None = None) -> int:
    ap = argparse.ArgumentParser(prog="run_pipeline")
    ap.add_argument("--prompt-version", default="v1")
    ap.add_argument("--only")
    ap.add_argument("--kind", choices=["trap", "realistic"])
    ap.add_argument("--report-dir", type=Path, default=EVALS_DIR / "reports")
    args = ap.parse_args(argv)

    if llm_factory is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY is not set: export it to run the real eval.", file=sys.stderr)
            return 2
        llm_factory = _anthropic

    goldens = _load_goldens(args.only, args.kind)
    if not goldens:
        print("No golden files matched.", file=sys.stderr)
        return 2
    settings = AISettings(prompt_version=args.prompt_version)
    scores, details = asyncio.run(_run(goldens, llm_factory(settings), settings))
    agg = aggregate(list(scores.values()))
    th = load_thresholds()

    print(f"{'metric':<26}{'value':>8}{'threshold':>11}  ok")
    for k, t in th.items():
        print(f"{k:<26}{agg[k]:>8.3f}{t:>11.2f}  {'Y' if agg[k] >= t else 'N'}")
    for n in agg["notes"]:
        print(f"note: {n}")
    print("PASS" if agg["pass"] else "FAIL")

    args.report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report = {"prompt_version": args.prompt_version, "aggregate": agg, "meetings": details}
    (args.report_dir / f"{stamp}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if agg["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
