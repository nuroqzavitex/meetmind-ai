from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.api_helpers import MAX_UPLOAD, FakeQueue
from tests.backend.auth_helpers import TEST_ISSUER, TEST_PARTY, make_jwks_cache

from app.ai.retrieval.embedder import HashEmbedder
from app.core.config import Settings
from app.main import create_app

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "transcripts"


@pytest.fixture
def transcript_bytes() -> bytes:
    return (FIXTURES / "payment_v2.txt").read_bytes()


@pytest.fixture
def queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
def app(sessionmaker: async_sessionmaker[AsyncSession], queue: FakeQueue) -> FastAPI:
    settings = Settings(
        _env_file=None,
        clerk_issuer=TEST_ISSUER,
        clerk_authorized_parties=[TEST_PARTY],
        max_upload_bytes=MAX_UPLOAD,
    )
    app = create_app(settings)
    app.state.sessionmaker = sessionmaker
    app.state.jwks = make_jwks_cache()
    app.state.queue = queue
    app.state.embedder = HashEmbedder(1024)
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as c:
        yield c
