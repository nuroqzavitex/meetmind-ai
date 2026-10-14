"""Discord bot: the Interactions Endpoint (signed by Discord, no Clerk) and admin bot settings."""

import json
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_discord, get_embedder, get_llm, get_principal, get_session
from app.core.auth import Principal
from app.core.errors import ServiceUnavailable, Unauthorized, Unprocessable
from app.notify.discord import DiscordClient
from app.notify.discord_bot import APPLICATION_COMMAND, PING, PONG, verify_signature
from app.schemas.settings import DiscordBotOut
from app.services import discord_bot as service

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]


@router.post("/discord/interactions", include_in_schema=False)
async def interactions(
    request: Request,
    background: BackgroundTasks,
    session: SessionDep,
    discord: Annotated[DiscordClient, Depends(get_discord)],
) -> dict[str, Any]:
    settings = request.app.state.settings
    if not settings.discord_public_key:
        raise ServiceUnavailable("Bot Discord chưa được cấu hình", "discord_bot_disabled")
    body = await request.body()
    signature = request.headers.get("X-Signature-Ed25519", "")
    timestamp = request.headers.get("X-Signature-Timestamp", "")
    if not verify_signature(settings.discord_public_key, signature, timestamp, body):
        raise Unauthorized("invalid request signature")
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise Unprocessable("Invalid JSON", "validation_error") from exc

    if payload.get("type") == PING:
        return {"type": PONG}
    if payload.get("type") != APPLICATION_COMMAND:
        return {"type": PONG}
    response, org_id, question = await service.handle_command(session, payload)
    if org_id is not None:
        background.add_task(
            service.answer_in_background,
            request.app.state.sessionmaker,
            discord,
            get_llm(request),
            get_embedder(request),
            settings.ai_settings(),
            org_id=org_id,
            payload=payload,
            question=question,
            app_url=settings.frontend_url.rstrip("/"),
        )
    return response


@router.get("/settings/discord-bot")
async def get_bot(request: Request, session: SessionDep, principal: PrincipalDep) -> DiscordBotOut:
    return await service.get_bot(session, request.app.state.settings, principal=principal)


@router.post("/settings/discord-bot/rotate-code")
async def rotate_code(
    request: Request, session: SessionDep, principal: PrincipalDep
) -> DiscordBotOut:
    return await service.rotate_code(session, request.app.state.settings, principal=principal)


@router.post("/settings/discord-bot/unlink")
async def unlink(request: Request, session: SessionDep, principal: PrincipalDep) -> DiscordBotOut:
    return await service.unlink(session, request.app.state.settings, principal=principal)
