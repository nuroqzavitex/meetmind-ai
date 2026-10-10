import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.models import Item, ItemEvent, Job, Meeting, Utterance

pytestmark = pytest.mark.db

TABLES = {
    "meetings",
    "utterances",
    "dialogue_acts",
    "topics",
    "items",
    "item_events",
    "jobs",
}


async def test_upgrade_creates_tables_and_extensions(migrated_db_url: str) -> None:
    engine = create_async_engine(migrated_db_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            exts = {r[0] for r in await conn.execute(text("SELECT extname FROM pg_extension"))}
            tables = {
                r[0]
                for r in await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
                    )
                )
            }
    finally:
        await engine.dispose()
    assert {"vector", "pg_trgm"} <= exts
    assert TABLES <= tables


async def test_models_match_migration(migrated_db_url: str) -> None:
    engine = create_async_engine(migrated_db_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:

            def diff(sync_conn):  # type: ignore[no-untyped-def]
                ctx = MigrationContext.configure(
                    sync_conn,
                    opts={
                        "include_object": lambda o, n, t, r, c: (
                            not (t == "table" and n == "alembic_version")
                        )
                    },
                )
                return compare_metadata(ctx, Base.metadata)

            assert await conn.run_sync(diff) == []
    finally:
        await engine.dispose()


async def test_meeting_cascade_delete(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    import datetime as dt

    async with sessionmaker() as s:
        s.add(
            Meeting(
                id="m1",
                org_id="o1",
                created_by="u",
                title="t",
                meeting_date=dt.date(2026, 1, 1),
                context={},
                source_filename="a.docx",
                source_bytes=b"x",
            )
        )
        await s.flush()
        s.add(Utterance(meeting_id="m1", id="u0001", seq=0, speaker="A", start=0.0, text="hi"))
        s.add(
            Item(
                id="m1-i001",
                org_id="o1",
                meeting_id="m1",
                type="decision",
                status="open",
                review_state="pending",
                data={},
                position=0,
            )
        )
        s.add(Job(id="j1", org_id="o1", kind="analyze", meeting_id="m1"))
        await s.flush()
        s.add(ItemEvent(item_id="m1-i001", actor_id="u", actor_name="U", action="created"))
        await s.commit()
    async with sessionmaker() as s:
        m = await s.get(Meeting, "m1")
        assert m is not None
        await s.delete(m)
        await s.commit()
        for model in (Utterance, Item, ItemEvent, Job, Meeting):
            assert await s.scalar(select(func.count()).select_from(model)) == 0
