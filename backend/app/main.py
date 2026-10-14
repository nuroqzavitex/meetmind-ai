"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.auth import JWKSCache, http_jwks_fetcher
from app.core.clerk_api import ClerkAPI
from app.core.config import Settings, get_settings
from app.core.errors import CatchAllMiddleware, install_error_handlers
from app.notify.discord import DiscordClient
from app.workers.queue import ArqQueue


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    engine = getattr(app.state, "engine", None)
    if engine is not None:
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="MeetMind AI", lifespan=_lifespan)
    app.state.settings = settings
    app.state.jwks = JWKSCache(http_jwks_fetcher(settings.clerk_jwks_url))
    app.state.queue = ArqQueue(settings.redis_url)
    app.state.discord = DiscordClient()
    key = settings.clerk_secret_key
    app.state.clerk = ClerkAPI(key.get_secret_value() if key else None)
    app.add_middleware(CatchAllMiddleware)  # inside CORS, so 500s keep CORS headers
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    install_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
