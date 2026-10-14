from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_discord, get_principal, get_session
from app.core.auth import Principal
from app.notify.discord import DiscordClient
from app.schemas.settings import DiscordSettingsIn, DiscordSettingsOut
from app.services import notifications as service

router = APIRouter(prefix="/settings")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
DiscordDep = Annotated[DiscordClient, Depends(get_discord)]


@router.get("/discord")
async def get_discord_settings(session: SessionDep, principal: PrincipalDep) -> DiscordSettingsOut:
    return await service.get_discord(session, principal=principal)


@router.put("/discord")
async def save_discord_settings(
    body: DiscordSettingsIn, session: SessionDep, principal: PrincipalDep
) -> DiscordSettingsOut:
    return await service.save_discord(session, principal=principal, body=body)


@router.post("/discord/test", status_code=204)
async def test_discord(session: SessionDep, principal: PrincipalDep, discord: DiscordDep) -> None:
    await service.send_test(session, discord, principal=principal)
