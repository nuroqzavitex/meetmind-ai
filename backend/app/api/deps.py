from fastapi import Request

from app.ai.llm import LLMClient
from app.ai.retrieval.embedder import Embedder
from app.core.auth import get_principal, get_user
from app.core.clerk_api import ClerkAPI
from app.core.embedding import build_embedder
from app.core.llm import UnconfiguredLLM, build_llm
from app.db.session import get_session
from app.notify.discord import DiscordClient
from app.workers.queue import get_queue

__all__ = [
    "get_clerk",
    "get_discord",
    "get_embedder",
    "get_llm",
    "get_principal",
    "get_queue",
    "get_session",
    "get_user",
]


def get_llm(request: Request) -> LLMClient:
    state = request.app.state
    if getattr(state, "llm", None) is None:
        llm = build_llm(state.settings)
        if isinstance(llm, UnconfiguredLLM):
            return llm  # not cached: a key added later is picked up
        state.llm = llm
    cached: LLMClient = state.llm
    return cached


def get_embedder(request: Request) -> Embedder:
    state = request.app.state
    if getattr(state, "embedder", None) is None:
        state.embedder = build_embedder(state.settings)
    embedder: Embedder = state.embedder
    return embedder


def get_discord(request: Request) -> DiscordClient:
    client: DiscordClient = request.app.state.discord
    return client


def get_clerk(request: Request) -> ClerkAPI:
    client: ClerkAPI = request.app.state.clerk
    return client
