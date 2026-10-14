"""CLI: ingest the golden meetings into a scratch Postgres and score knowledge Q&A."""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  (register tables on Base.metadata)
from alembic import command
from app.ai.config import AISettings
from app.ai.domain.enums import ReviewState
from app.ai.domain.models import Utterance
from app.ai.llm.client import AnthropicLLM, LLMClient
from app.ai.pipeline import analyze_transcript
from app.ai.retrieval.embedder import Embedder, make_embedder
from app.core.auth import Principal
from app.core.config import Settings
from app.db.base import Base
from app.db.session import make_sessionmaker
from app.repositories import items, jobs, meetings
from app.schemas.qa import QAResponse
from app.services import qa
from app.services.indexing import run_index
from evals.metrics.matching import Golden
from evals.metrics.qa import QAQuestion, load_qa_thresholds, score

EVALS_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = EVALS_DIR.parent / "backend"
QUESTIONS_PATH = EVALS_DIR / "datasets" / "qa" / "questions.json"
DEFAULT_DB_URL = "postgresql+asyncpg://app:app@localhost:5432/meeting_test"
ORG_ID = "eval_org"
LLMFactory = Callable[[AISettings], LLMClient]


def _anthropic(settings: AISettings) -> LLMClient:
    return AnthropicLLM(settings)


def _load_questions(only: str | None) -> list[QAQuestion]:
    raw = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    qs = [QAQuestion.model_validate(x) for x in raw]
    return [q for q in qs if not only or q.id == only]


def _load_golden(name: str) -> Golden:
    path = EVALS_DIR / "golden" / f"{name}.json"
    return Golden.model_validate_json(path.read_text(encoding="utf-8"))


class IndexFailed(RuntimeError):
    """The index job of an eval meeting did not succeed."""


async def _check_reachable(url: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


async def _reset_schema(url: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
            await conn.run_sync(Base.metadata.drop_all)
    finally:
        await engine.dispose()


def _migrate(url: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["url"] = url
    command.upgrade(cfg, "head")


async def _ingest(
    sm: async_sessionmaker[AsyncSession],
    embedder: Embedder,
    llm: LLMClient,
    ai: AISettings,
    name: str,
) -> list[Utterance]:
    """Analyse one golden meeting, approve every item, publish it and run the index job."""
    g = _load_golden(name)
    data = (EVALS_DIR / g.transcript).read_bytes()
    filename = Path(g.transcript).name
    res = await analyze_transcript(
        ctx=g.context, filename=filename, data=data, llm=llm, settings=ai
    )
    mid = g.context.meeting_id
    async with sm() as s:
        await meetings.create(
            s, org_id=ORG_ID, created_by="eval", ctx=g.context, filename=filename, data=data
        )
        await meetings.replace_analysis(
            s, org_id=ORG_ID, meeting_id=mid,
            utterances=res.utterances, acts=res.acts, topics=res.topics,
        )
        approved = [i.model_copy(update={"review_state": ReviewState.APPROVED}) for i in res.items]
        await items.replace_for_meeting(s, org_id=ORG_ID, meeting_id=mid, items=approved)
        await meetings.set_status(s, org_id=ORG_ID, meeting_id=mid, status="published")
        job = await jobs.create(s, org_id=ORG_ID, meeting_id=mid, kind="index")
        await s.commit()
        job_id = job.id
    await run_index(sm, embedder, org_id=ORG_ID, meeting_id=mid, job_id=job_id)
    async with sm() as s:
        done = await jobs.get(s, org_id=ORG_ID, job_id=job_id)
    if done is None or done.status != "succeeded":
        raise IndexFailed(f"Indexing {name} failed: {done.error if done else 'job missing'}")
    return res.utterances


WINDOW = 6  # utterances per transcript chunk


def make_window(
    utterances: dict[str, list[Utterance]],
) -> Callable[[str, str], str]:
    """Lookup (meeting_id, utterance_id) -> text of WINDOW utterances starting there."""

    def window(meeting_id: str, utterance_id: str) -> str:
        utts = utterances.get(meeting_id, [])
        start = next((i for i, u in enumerate(utts) if u.id == utterance_id), None)
        if start is None:
            return ""
        return "\n".join(f"{u.speaker}: {u.text}" for u in utts[start : start + WINDOW])

    return window


async def _run(
    questions: list[QAQuestion], llm: LLMClient, ai: AISettings, url: str, provider: str
) -> tuple[list[tuple[QAQuestion, QAResponse]], Callable[[str, str], str]]:
    engine = create_async_engine(url, poolclass=NullPool)
    sm = make_sessionmaker(engine)
    cfg = Settings()
    key = cfg.gemini_api_key
    embedder = make_embedder(
        provider,
        cfg.embedding_model,
        cfg.embedding_dim,
        api_key=key.get_secret_value() if key else None,
    )
    principal = Principal(user_id="eval", org_id=ORG_ID, name="Eval")
    results: list[tuple[QAQuestion, QAResponse]] = []
    utterances: dict[str, list[Utterance]] = {}
    try:
        for name in sorted({m for q in questions for m in q.meetings}):
            print(f"ingest {name}", file=sys.stderr)
            utterances[_load_golden(name).context.meeting_id] = await _ingest(
                sm, embedder, llm, ai, name
            )
        for q in questions:
            async with sm() as session:
                resp = await qa.ask(
                    session, llm, embedder, ai,
                    principal=principal, question=q.question, project=None, today=date.today(),
                )
            results.append((q, resp))
    finally:
        await engine.dispose()
    return results, make_window(utterances)


def _validate_db(url: str) -> str | None:
    """Return an error message when the DB is unsafe or unreachable, else None."""
    db_name = make_url(url).database or ""
    if not db_name.endswith("_test"):
        return f"Refusing to reset database {db_name!r}: TEST_DATABASE_URL must end with '_test'."
    try:
        asyncio.run(_check_reachable(url))
    except Exception as exc:  # noqa: BLE001
        reason = " ".join(str(exc).split())[:120]
        return f"Postgres not reachable at TEST_DATABASE_URL ({reason}): docker compose up -d db."
    return None


def main(argv: list[str] | None = None, llm_factory: LLMFactory | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="run_qa")
    ap.add_argument("--only", help="run a single question id")
    ap.add_argument("--embedder", choices=["local", "hash", "gemini"], default="local")
    ap.add_argument("--prompt-version", default="v1")
    ap.add_argument("--report-dir", type=Path, default=EVALS_DIR / "reports")
    args = ap.parse_args(argv)

    if llm_factory is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY is not set: export it to run the real eval.", file=sys.stderr)
            return 2
        llm_factory = _anthropic

    questions = _load_questions(args.only)
    if not questions:
        print("No questions matched.", file=sys.stderr)
        return 2

    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_DB_URL)
    problem = _validate_db(url)
    if problem:
        print(problem, file=sys.stderr)
        return 2

    ai = AISettings(prompt_version=args.prompt_version)
    asyncio.run(_reset_schema(url))
    _migrate(url)
    try:
        results, window = asyncio.run(_run(questions, llm_factory(ai), ai, url, args.embedder))
    except IndexFailed as exc:
        print(" ".join(str(exc).split()), file=sys.stderr)
        return 2

    scores = score(results, window)
    th = load_qa_thresholds()
    ok = all(scores[k] >= t for k, t in th.items() if k in scores)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "prompt_version": args.prompt_version,
        "embedder": args.embedder,
        "scores": scores,
        "pass": ok,
        "results": [
            {
                "id": q.id,
                "kind": q.kind,
                "question": q.question,
                "response": r.model_dump(mode="json"),
            }
            for q, r in results
        ],
    }
    (args.report_dir / f"qa-{stamp}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for q, r in results:
        print(f"[{q.kind}] {q.id}: {r.answer}")
        for c in r.citations:
            print(f"    [{c.ref}] {c.title} {c.ts} {c.speaker}: {c.quote}")
    print(f"{'metric':<28}{'value':>8}{'threshold':>11}  ok")
    for k, t in th.items():
        if k in scores:
            print(f"{k:<28}{scores[k]:>8.3f}{t:>11.2f}  {'Y' if scores[k] >= t else 'N'}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
