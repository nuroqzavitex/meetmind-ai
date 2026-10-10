"""Engine / sessionmaker helpers and the FastAPI session dependency."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def make_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a session; the sessionmaker is created lazily and cached on app.state."""
    app = request.app
    sm: async_sessionmaker[AsyncSession] | None = getattr(app.state, "sessionmaker", None)
    if sm is None:
        engine = make_engine(app.state.settings.database_url)
        app.state.engine = engine
        sm = make_sessionmaker(engine)
        app.state.sessionmaker = sm
    async with sm() as session:
        yield session
