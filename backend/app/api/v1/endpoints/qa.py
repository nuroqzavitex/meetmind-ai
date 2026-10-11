from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import LLMClient
from app.ai.retrieval.embedder import Embedder
from app.api.deps import get_embedder, get_llm, get_principal, get_session
from app.core.auth import Principal
from app.schemas.qa import QARequest, QAResponse
from app.services import qa as service

router = APIRouter(prefix="/qa")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]


@router.post("")
async def ask(
    body: QARequest,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
    llm: LLMDep,
    embedder: EmbedderDep,
) -> QAResponse:
    return await service.ask(
        session,
        llm,
        embedder,
        request.app.state.settings.ai_settings(),
        principal=principal,
        question=body.question,
        project=body.project,
        today=date.today(),
    )
