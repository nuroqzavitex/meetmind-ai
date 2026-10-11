import datetime as dt

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.pipeline_helpers import (
    seed_published_indexed_meeting,
)

from app.ai.retrieval.embedder import HashEmbedder
from app.models import Item, Meeting, TranscriptChunk
from app.repositories.search import (
    SearchFilters,
    hybrid_search,
    load_chunks,
    load_items,
    meetings_by_id,
    org_projects,
    search_chunks_keyword,
    search_chunks_vector,
    search_items_keyword,
    search_items_vector,
)
from app.services.indexing import run_index

pytestmark = pytest.mark.db
EMB = HashEmbedder(1024)
PG = "dùng Postgres cho thanh toán"


async def _seed_b(sm: async_sessionmaker[AsyncSession]) -> None:
    async with sm() as s:
        s.add(
            Meeting(
                id="mb",
                org_id="org_b",
                created_by="u",
                title="CRM",
                meeting_date=dt.date(2026, 10, 9),
                project="crm",
                context={},
                status="published",
                source_filename="x.txt",
                source_bytes=b"x",
            )
        )
        await s.flush()
        s.add(
            Item(
                id="ib",
                org_id="org_b",
                meeting_id="mb",
                type="decision",
                status="active",
                review_state="approved",
                data={
                    "id": "ib",
                    "meeting_id": "mb",
                    "type": "decision",
                    "content": "Chốt dùng MongoDB cho CRM",
                    "owner": "An",
                    "evidence": [{"utterance_id": "u1", "speaker": "An", "quote": "MongoDB"}],
                },
                position=0,
            )
        )
        s.add(
            TranscriptChunk(
                id="cb",
                org_id="org_b",
                meeting_id="mb",
                seq=0,
                start_ts=0.0,
                end_ts=5.0,
                first_utterance_id="u1",
                speakers=["An"],
                text="An: Chốt dùng MongoDB cho CRM",
            )
        )
        await s.commit()
    from app.repositories import jobs

    async with sm() as s:
        job = await jobs.create(s, org_id="org_b", meeting_id="mb", kind="index")
        await s.commit()
        jid = job.id
    await run_index(sm, EMB, org_id="org_b", meeting_id="mb", job_id=jid)


async def _setup(sm: async_sessionmaker[AsyncSession]) -> dict[str, list[str]]:
    await seed_published_indexed_meeting(sm, EMB, "org_a", "m1", project="thanh toán")
    await seed_published_indexed_meeting(sm, EMB, "org_a", "m2")
    await _seed_b(sm)
    async with sm() as s:
        await s.execute(update(Meeting).where(Meeting.id == "m2").values(status="in_review"))
        ids = list(
            await s.scalars(select(Item.id).where(Item.meeting_id == "m1").order_by(Item.position))
        )
        assert len(ids) >= 3
        await s.execute(update(Item).where(Item.id == ids[0]).values(review_state="rejected"))
        await s.execute(update(Item).where(Item.id == ids[1]).values(review_state="pending"))
        m2_items = list(await s.scalars(select(Item.id).where(Item.meeting_id == "m2")))
        m2_chunks = list(
            await s.scalars(select(TranscriptChunk.id).where(TranscriptChunk.meeting_id == "m2"))
        )
        assert m2_items and m2_chunks
        await s.commit()
    return {"bad": ids[:2], "m2_items": m2_items, "m2_chunks": m2_chunks}


async def test_hybrid_scoping_and_filters(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    seeded = await _setup(sessionmaker)
    async with sessionmaker() as s:
        qv = (await EMB.embed([PG]))[0]
        hits = await hybrid_search(
            s, org_id="org_a", query=PG, query_vec=qv, filters=SearchFilters()
        )
        assert hits and len(hits) <= 12
        assert {h.meeting_id for h in hits} == {"m1"}
        hit_ids = {h.id for h in hits}
        assert not hit_ids & set(seeded["bad"])
        assert not hit_ids & set(seeded["m2_items"] + seeded["m2_chunks"])
        items = await load_items(s, org_id="org_a", ids=[h.id for h in hits if h.kind == "item"])
        assert any(
            i.type == "decision" and "Postgres" in (i.search_text or "") for i in items.values()
        )

        qb = (await EMB.embed(["Postgres thanh toán"]))[0]
        hb = await hybrid_search(
            s, org_id="org_b", query="Postgres thanh toán", query_vec=qb, filters=SearchFilters()
        )
        assert {h.meeting_id for h in hb} <= {"mb"}

        none = await hybrid_search(
            s, org_id="org_a", query=PG, query_vec=qv, filters=SearchFilters(project="khác")
        )
        assert none == []

        acts = await hybrid_search(
            s,
            org_id="org_a",
            query=PG,
            query_vec=qv,
            filters=SearchFilters(item_types=["action_item"]),
        )
        got = await load_items(s, org_id="org_a", ids=[h.id for h in acts if h.kind == "item"])
        assert got and all(i.type == "action_item" for i in got.values())

        assert await org_projects(s, org_id="org_a") == ["thanh toán"]


async def test_date_and_people_filters(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await _setup(sessionmaker)
    async with sessionmaker() as s:
        qv = (await EMB.embed([PG]))[0]
        late = await hybrid_search(
            s,
            org_id="org_a",
            query=PG,
            query_vec=qv,
            filters=SearchFilters(date_from=dt.date(2027, 1, 1)),
        )
        assert late == []
        ghost = await hybrid_search(
            s, org_id="org_a", query=PG, query_vec=qv, filters=SearchFilters(people=["nobody"])
        )
        assert ghost == []
        lan = await hybrid_search(
            s, org_id="org_a", query=PG, query_vec=qv, filters=SearchFilters(people=["LAN"])
        )
        assert lan


async def test_loaders_exclude_unpublished_and_unapproved(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    seeded = await _setup(sessionmaker)
    async with sessionmaker() as s:
        assert await load_items(s, org_id="org_a", ids=seeded["m2_items"] + seeded["bad"]) == {}
        assert await load_chunks(s, org_id="org_a", ids=seeded["m2_chunks"]) == {}
        assert await meetings_by_id(s, org_id="org_a", ids=["m2"]) == {}
        assert set(await meetings_by_id(s, org_id="org_a", ids=["m1", "m2"])) == {"m1"}


async def test_date_range_inclusive(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await _setup(sessionmaker)
    async with sessionmaker() as s:
        qv = (await EMB.embed([PG]))[0]
        day = dt.date(2026, 10, 8)
        hits = await hybrid_search(
            s,
            org_id="org_a",
            query=PG,
            query_vec=qv,
            filters=SearchFilters(date_from=day, date_to=day),
        )
        assert hits


async def test_raw_searches_exclude_unpublished_and_unapproved(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    seeded = await _setup(sessionmaker)
    async with sessionmaker() as s:
        qv = (await EMB.embed([PG]))[0]
        f = SearchFilters()
        iv = await search_items_vector(s, org_id="org_a", query_vec=qv, filters=f)
        ik = await search_items_keyword(s, org_id="org_a", query=PG, filters=f)
        cv = await search_chunks_vector(s, org_id="org_a", query_vec=qv, filters=f)
        ck = await search_chunks_keyword(s, org_id="org_a", query=PG, filters=f)
        assert iv and cv and ik
        bad_items = set(seeded["m2_items"]) | set(seeded["bad"])
        assert not set(iv) & bad_items and not set(ik) & bad_items
        assert not set(cv) & set(seeded["m2_chunks"])
        assert not set(ck) & set(seeded["m2_chunks"])
