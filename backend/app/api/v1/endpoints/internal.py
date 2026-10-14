"""Endpoints called by schedulers, not by users; guarded by CRON_SECRET instead of Clerk."""

import secrets
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_discord, get_session
from app.core.errors import ServiceUnavailable, Unauthorized
from app.notify.discord import DiscordClient
from app.schemas.settings import DigestOut
from app.services import notifications as service

router = APIRouter(prefix="/internal", include_in_schema=False)

# Vietnam has no daylight saving time; a fixed offset avoids needing tzdata on Windows.
VN_TZ = timezone(timedelta(hours=7))


@router.post("/digest")
async def digest(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    discord: Annotated[DiscordClient, Depends(get_discord)],
    x_cron_secret: Annotated[str, Header()] = "",
    on: date | None = None,
) -> DigestOut:
    settings = request.app.state.settings
    expected = settings.cron_secret.get_secret_value() if settings.cron_secret else ""
    if not expected:
        raise ServiceUnavailable("Bản tin chưa được bật (thiếu CRON_SECRET)", "digest_disabled")
    if not secrets.compare_digest(x_cron_secret.encode(), expected.encode()):
        raise Unauthorized("Sai CRON_SECRET")
    today = on or datetime.now(UTC).astimezone(VN_TZ).date()
    return await service.run_digest(
        session, discord, today=today, app_url=settings.frontend_url.rstrip("/")
    )
