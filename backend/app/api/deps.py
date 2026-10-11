from typing import Any

from fastapi import Request

from app.ai.errors import LLMError
from app.ai.llm import LLMClient
from app.ai.llm.factory import make_llm
from app.ai.retrieval.embedder import Embedder, make_embedder
from app.core.auth import get_principal
from app.db.session import get_session
from app.workers.queue import get_queue

__all__ = ["get_embedder", "get_llm", "get_principal", "get_queue", "get_session"]


class _UnconfiguredLLM:
    """Stands in when no API key is set; fails only when an LLM call is actually made."""

    async def structured(self, **_: Any) -> Any:
        raise LLMError("ANTHROPIC_API_KEY chưa được cấu hình")


def get_llm(request: Request) -> LLMClient:
    state = request.app.state
    if getattr(state, "llm", None) is None:
        settings = state.settings
        key = settings.anthropic_api_key
        if key is None:
            return _UnconfiguredLLM()
        state.llm = make_llm(settings.ai_settings(), key.get_secret_value())
    llm: LLMClient = state.llm
    return llm


def get_embedder(request: Request) -> Embedder:
    state = request.app.state
    if getattr(state, "embedder", None) is None:
        s = state.settings
        state.embedder = make_embedder(s.embedding_provider, s.embedding_model, s.embedding_dim)
    embedder: Embedder = state.embedder
    return embedder
