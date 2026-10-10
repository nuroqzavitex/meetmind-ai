"""Shared fixtures: Postgres-backed test database (skipped when unreachable)."""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  (register tables on Base.metadata)
from alembic import command
from app.db.base import Base
from app.db.session import make_sessionmaker

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/meeting_test"
)
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"


async def _reset_schema(url: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
            await conn.run_sync(Base.metadata.drop_all)
    finally:
        await engine.dispose()


async def _check_reachable(url: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def migrated_db_url() -> Iterator[str]:
    try:
        asyncio.run(_check_reachable(TEST_DATABASE_URL))
    except Exception as exc:  # noqa: BLE001
        msg = "Postgres not reachable — run `docker compose up -d db`"
        if os.environ.get("REQUIRE_DB") == "1":
            pytest.fail(f"{msg} ({exc})")
        pytest.skip(msg)
    db_name = make_url(TEST_DATABASE_URL).database or ""
    if not db_name.endswith("_test"):
        pytest.fail(
            f"Refusing to reset database {db_name!r}: TEST_DATABASE_URL must point to a "
            "database whose name ends with '_test'"
        )
    asyncio.run(_reset_schema(TEST_DATABASE_URL))
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["url"] = TEST_DATABASE_URL
    command.upgrade(cfg, "head")
    yield TEST_DATABASE_URL


@pytest.fixture
async def sessionmaker(migrated_db_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(migrated_db_url, poolclass=NullPool)
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield make_sessionmaker(engine)
    await engine.dispose()
