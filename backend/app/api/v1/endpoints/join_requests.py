from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_clerk, get_discord, get_principal, get_session, get_user
from app.core.auth import Principal, User
from app.core.clerk_api import ClerkAPI
from app.notify.discord import DiscordClient
from app.schemas.join_requests import JoinCodeOut, JoinRequestIn, JoinRequestOut
from app.services import join_requests as service

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
UserDep = Annotated[User, Depends(get_user)]
ClerkDep = Annotated[ClerkAPI, Depends(get_clerk)]


@router.get("/settings/join-code")
async def get_join_code(session: SessionDep, principal: PrincipalDep) -> JoinCodeOut:
    return await service.get_join_code(session, principal=principal)


@router.post("/settings/join-code/rotate")
async def rotate_join_code(session: SessionDep, principal: PrincipalDep) -> JoinCodeOut:
    return await service.rotate_join_code(session, principal=principal)


# --- the person asking to join: no active organization required ---


@router.post("/join-requests", status_code=201)
async def create_join_request(
    body: JoinRequestIn,
    request: Request,
    background: BackgroundTasks,
    session: SessionDep,
    user: UserDep,
    clerk: ClerkDep,
    discord: Annotated[DiscordClient, Depends(get_discord)],
) -> JoinRequestOut:
    out, webhook = await service.create(session, clerk, user=user, raw_code=body.code)
    if webhook:
        app_url = request.app.state.settings.frontend_url.rstrip("/")
        background.add_task(service.notify_discord, discord, webhook, out, app_url)
    return out


@router.get("/join-requests/mine")
async def my_join_requests(session: SessionDep, user: UserDep) -> list[JoinRequestOut]:
    return await service.list_mine(session, user=user)


@router.delete("/join-requests/{request_id}", status_code=204)
async def cancel_join_request(request_id: str, session: SessionDep, user: UserDep) -> None:
    await service.cancel(session, user=user, request_id=request_id)


# --- admins of the active organization ---


@router.get("/join-requests")
async def pending_join_requests(
    session: SessionDep, principal: PrincipalDep
) -> list[JoinRequestOut]:
    return await service.list_pending(session, principal=principal)


@router.post("/join-requests/{request_id}/approve")
async def approve_join_request(
    request_id: str, session: SessionDep, principal: PrincipalDep, clerk: ClerkDep
) -> JoinRequestOut:
    return await service.decide(
        session, clerk, principal=principal, request_id=request_id, approve=True
    )


@router.post("/join-requests/{request_id}/reject")
async def reject_join_request(
    request_id: str, session: SessionDep, principal: PrincipalDep, clerk: ClerkDep
) -> JoinRequestOut:
    return await service.decide(
        session, clerk, principal=principal, request_id=request_id, approve=False
    )
