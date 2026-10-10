"""Arq worker entrypoint: `arq app.workers.main.WorkerSettings`."""

from typing import Any

from arq.connections import RedisSettings

from app.ai.llm.factory import make_llm
from app.core.config import JOB_TIMEOUT_SECONDS, get_settings
from app.db.session import make_engine, make_sessionmaker
from app.services.analysis import run_analysis


async def analyze(ctx: dict[str, Any], *, org_id: str, meeting_id: str, job_id: str) -> None:
    await run_analysis(
        ctx["sessionmaker"], ctx["llm"], ctx["ai"],
        org_id=org_id, meeting_id=meeting_id, job_id=job_id,
    )


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    ctx["engine"] = make_engine(settings.database_url)
    ctx["sessionmaker"] = make_sessionmaker(ctx["engine"])
    ctx["ai"] = settings.ai_settings()
    key = settings.anthropic_api_key
    ctx["llm"] = make_llm(ctx["ai"], key.get_secret_value() if key else None)


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["engine"].dispose()


class WorkerSettings:
    functions = [analyze]  # noqa: RUF012
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 1
    job_timeout = JOB_TIMEOUT_SECONDS
