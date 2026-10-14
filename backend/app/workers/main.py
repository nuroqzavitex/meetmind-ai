"""Arq worker entrypoint: `arq app.workers.main.WorkerSettings`."""

from typing import Any

from arq.connections import RedisSettings

from app.core.config import JOB_TIMEOUT_SECONDS, get_settings
from app.core.embedding import build_embedder
from app.core.llm import build_llm
from app.core.stt import build_stt
from app.db.session import make_engine, make_sessionmaker
from app.notify.discord import DiscordClient
from app.services.analysis import run_analysis
from app.services.indexing import run_index
from app.services.notifications import notify_published
from app.services.transcription import run_transcription


async def analyze(ctx: dict[str, Any], *, org_id: str, meeting_id: str, job_id: str) -> None:
    await run_analysis(
        ctx["sessionmaker"], ctx["llm"], ctx["ai"],
        org_id=org_id, meeting_id=meeting_id, job_id=job_id,
    )


async def transcribe(ctx: dict[str, Any], *, org_id: str, meeting_id: str, job_id: str) -> None:
    await run_transcription(
        ctx["sessionmaker"], ctx["stt"],
        org_id=org_id, meeting_id=meeting_id, job_id=job_id,
    )


async def index(ctx: dict[str, Any], *, org_id: str, meeting_id: str, job_id: str) -> None:
    await run_index(
        ctx["sessionmaker"], ctx["embedder"],
        org_id=org_id, meeting_id=meeting_id, job_id=job_id,
    )


async def notify(ctx: dict[str, Any], *, org_id: str, meeting_id: str, job_id: str) -> None:
    await notify_published(
        ctx["sessionmaker"], ctx["discord"],
        org_id=org_id, meeting_id=meeting_id, app_url=ctx["frontend_url"],
    )


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    ctx["engine"] = make_engine(settings.database_url)
    ctx["sessionmaker"] = make_sessionmaker(ctx["engine"])
    ctx["ai"] = settings.ai_settings()
    ctx["llm"] = build_llm(settings)
    ctx["stt"] = build_stt(settings)
    ctx["embedder"] = build_embedder(settings)
    ctx["discord"] = DiscordClient()
    ctx["frontend_url"] = settings.frontend_url.rstrip("/")


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["engine"].dispose()


class WorkerSettings:
    functions = [analyze, index, notify, transcribe]  # noqa: RUF012
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 1
    job_timeout = JOB_TIMEOUT_SECONDS
    poll_delay = get_settings().worker_poll_delay
