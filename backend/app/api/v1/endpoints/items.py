from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_principal, get_session
from app.core.auth import Principal
from app.schemas.items import ItemAction, ItemEventOut, ItemOut
from app.services import publish as publish_service
from app.services import review as service

router = APIRouter(prefix="/items")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]


@router.patch("/{item_id}")
async def act_on_item(
    item_id: str, body: ItemAction, session: SessionDep, principal: PrincipalDep
) -> ItemOut:
    item = await service.act_on_item(session, principal=principal, item_id=item_id, action=body)
    return ItemOut.model_validate(item.model_dump())


@router.get("/{item_id}/events")
async def list_events(
    item_id: str, session: SessionDep, principal: PrincipalDep
) -> list[ItemEventOut]:
    return await service.list_events(session, principal=principal, item_id=item_id)


class ReportIn(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class ReopenIn(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


@router.post("/{item_id}/report", status_code=204)
async def report_item(
    item_id: str, body: ReportIn, session: SessionDep, principal: PrincipalDep
) -> Response:
    await publish_service.report_item(
        session, principal=principal, item_id=item_id, reason=body.reason
    )
    return Response(status_code=204)


@router.post("/{item_id}/reopen")
async def reopen_item(
    item_id: str, session: SessionDep, principal: PrincipalDep, body: ReopenIn | None = None
) -> ItemOut:
    item = await publish_service.reopen_item(
        session, principal=principal, item_id=item_id, reason=body.reason if body else None
    )
    return ItemOut.model_validate(item.model_dump())
