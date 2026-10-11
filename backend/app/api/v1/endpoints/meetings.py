from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_principal, get_queue, get_session
from app.core.auth import Principal
from app.core.errors import Unprocessable
from app.schemas.items import ApproveCleanOut, ItemOut, TopicOut
from app.schemas.meetings import (
    MeetingContextIn,
    MeetingCreated,
    MeetingDetail,
    MeetingSummary,
)
from app.services import meetings as service
from app.services import publish as publish_service
from app.services import review
from app.workers.queue import JobQueue

router = APIRouter(prefix="/meetings")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
QueueDep = Annotated[JobQueue, Depends(get_queue)]


@router.post("", status_code=201)
async def create_meeting(
    request: Request,
    session: SessionDep,
    queue: QueueDep,
    principal: PrincipalDep,
    file: Annotated[UploadFile, File()],
    context: Annotated[str, Form()],
) -> MeetingCreated:
    try:
        ctx_in = MeetingContextIn.model_validate_json(context)
    except ValidationError as exc:
        parts = [f"context.{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise Unprocessable("; ".join(parts), "validation_error") from exc
    max_bytes: int = request.app.state.settings.max_upload_bytes
    data = await file.read(max_bytes + 1)
    return await service.create_meeting(
        session,
        queue,
        principal=principal,
        ctx_in=ctx_in,
        filename=file.filename or "",
        data=data,
        max_bytes=max_bytes,
    )


@router.get("")
async def list_meetings(
    session: SessionDep,
    principal: PrincipalDep,
    project: str | None = None,
    status: str | None = None,
) -> list[MeetingSummary]:
    return await service.list_meetings(session, principal=principal, project=project, status=status)


@router.get("/{meeting_id}")
async def get_meeting(
    meeting_id: str, session: SessionDep, principal: PrincipalDep
) -> MeetingDetail:
    return await service.get_meeting(session, principal=principal, meeting_id=meeting_id)


@router.post("/{meeting_id}/reanalyze", status_code=202)
async def reanalyze(
    meeting_id: str, session: SessionDep, queue: QueueDep, principal: PrincipalDep
) -> MeetingCreated:
    return await service.reanalyze(session, queue, principal=principal, meeting_id=meeting_id)


@router.get("/{meeting_id}/items")
async def list_items(
    meeting_id: str, session: SessionDep, principal: PrincipalDep
) -> list[ItemOut]:
    rows = await review.list_items(session, principal=principal, meeting_id=meeting_id)
    return [ItemOut.model_validate(r.model_dump()) for r in rows]


@router.get("/{meeting_id}/topics")
async def list_topics(
    meeting_id: str, session: SessionDep, principal: PrincipalDep
) -> list[TopicOut]:
    rows = await review.list_topics(session, principal=principal, meeting_id=meeting_id)
    return [TopicOut.model_validate(r.model_dump()) for r in rows]


@router.post("/{meeting_id}/items/approve-clean")
async def approve_clean(
    meeting_id: str, session: SessionDep, principal: PrincipalDep
) -> ApproveCleanOut:
    n = await review.approve_clean(session, principal=principal, meeting_id=meeting_id)
    return ApproveCleanOut(approved=n)


@router.post("/{meeting_id}/publish")
async def publish(
    meeting_id: str, session: SessionDep, queue: QueueDep, principal: PrincipalDep
) -> MeetingSummary:
    return await publish_service.publish(
        session, queue, principal=principal, meeting_id=meeting_id
    )


@router.get("/{meeting_id}/export")
async def export_meeting(
    meeting_id: str,
    session: SessionDep,
    principal: PrincipalDep,
    format: Literal["md", "json"] = "md",
) -> Response:
    body, media_type, filename = await publish_service.export(
        session, principal=principal, meeting_id=meeting_id, fmt=format
    )
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
