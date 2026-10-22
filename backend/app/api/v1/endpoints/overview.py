from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_discord, get_principal, get_session
from app.core.auth import Principal
from app.notify.discord import DiscordClient
from app.schemas.overview import AgendaOut, AgendaSentOut, DecisionsOut, TasksOut
from app.services import overview as service

router = APIRouter(prefix="/overview", tags=["overview"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
ProjectQ = Annotated[str | None, Query(max_length=200)]


@router.get("/agenda")
async def agenda(session: SessionDep, principal: PrincipalDep, project: ProjectQ = None) -> AgendaOut:
    return await service.get_agenda(
        session, principal=principal, project=project or None, today=service.vn_today()
    )


@router.post("/agenda/discord")
async def send_agenda(
    session: SessionDep,
    principal: PrincipalDep,
    discord: Annotated[DiscordClient, Depends(get_discord)],
    project: ProjectQ = None,
) -> AgendaSentOut:
    await service.send_agenda(
        session, discord, principal=principal, project=project or None, today=service.vn_today()
    )
    return AgendaSentOut(sent=True)


@router.get("/tasks")
async def tasks(
    session: SessionDep,
    principal: PrincipalDep,
    project: ProjectQ = None,
    owner: Annotated[str | None, Query(max_length=200)] = None,
) -> TasksOut:
    return await service.get_tasks(
        session, principal=principal, project=project or None, owner=owner or None,
        today=service.vn_today(),
    )


@router.get("/decisions")
async def decisions(
    session: SessionDep, principal: PrincipalDep, project: ProjectQ = None
) -> DecisionsOut:
    return await service.get_decisions(
        session, principal=principal, project=project or None, today=service.vn_today()
    )
