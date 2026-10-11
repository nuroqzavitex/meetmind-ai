"""Arq worker entrypoint: `arq app.workers.main.WorkerSettings`."""

from typing import Any

from arq.connections import RedisSettings

from app.ai.retrieval.embedder import make_embedder
from app.core.config import JOB_TIMEOUT_SECONDS, get_settings
from app.core.llm import build_llm
from app.db.session import make_engine, make_sessionmaker
from app.services.analysis import run_analysis
from app.services.indexing import run_index


async def analyze(ctx: dict[str, Any], *, org_id: str, meeting_id: str, job_id: str) -> None:
    await run_analysis(
        ctx["sessionmaker"], ctx["llm"], ctx["ai"],
        org_id=org_id, meeting_id=meeting_id, job_id=job_id,
    )


async def index(ctx: dict[str, Any], *, org_id: str, meeting_id: str, job_id: str) -> None:
    await run_index(
        ctx["sessionmaker"], ctx["embedder"],
        org_id=org_id, meeting_id=meeting_id, job_id=job_id,
    )


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    ctx["engine"] = make_engine(settings.database_url)
    ctx["sessionmaker"] = make_sessionmaker(ctx["engine"])
    ctx["ai"] = settings.ai_settings()
    ctx["llm"] = build_llm(settings)
    ctx["embedder"] = make_embedder(
        settings.embedding_provider, settings.embedding_model, settings.embedding_dim
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["engine"].dispose()


class WorkerSettings:
    functions = [analyze, index]  # noqa: RUF012
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 1
    job_timeout = JOB_TIMEOUT_SECONDS
