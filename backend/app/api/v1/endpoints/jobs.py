from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_principal, get_session
from app.core.auth import Principal
from app.schemas.jobs import JobOut
from app.services import meetings as service

router = APIRouter(prefix="/jobs")


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_principal)],
) -> JobOut:
    return await service.get_job(session, principal=principal, job_id=job_id)
