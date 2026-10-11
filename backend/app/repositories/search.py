from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from sqlalchemy import ColumnElement, and_, column, exists, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.ai.retrieval.rrf import rrf_fuse
from app.models import Item, Meeting, TranscriptChunk

KEYWORD_THRESHOLD = 0.2


@dataclass
class SearchFilters:
    project: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    people: list[str] = field(default_factory=list)
    item_types: list[str] = field(default_factory=list)


@dataclass
class Hit:
    kind: Literal["item", "chunk"]
    id: str
    meeting_id: str


def _meeting_conds(org_id: str, f: SearchFilters) -> list[ColumnElement[bool]]:
    conds: list[ColumnElement[bool]] = [
        Meeting.org_id == org_id,
        Meeting.status == "published",
    ]
    if f.project is not None:
        conds.append(Meeting.project == f.project)
    if f.date_from is not None:
        conds.append(Meeting.meeting_date >= f.date_from)
    if f.date_to is not None:
        conds.append(Meeting.meeting_date <= f.date_to)
    return conds


def _people(f: SearchFilters) -> list[str]:
    return [p.casefold() for p in f.people]


def _item_stmt(org_id: str, f: SearchFilters) -> Select[Any]:
    conds: list[ColumnElement[bool]] = [
        Item.org_id == org_id,
        Item.review_state.in_(("approved", "edited")),
        Item.embedding.is_not(None),
        Item.search_text.is_not(None),
        *_meeting_conds(org_id, f),
    ]
    if f.item_types:
        conds.append(Item.type.in_(f.item_types))
    people = _people(f)
    if people:
        ev = (
            func.jsonb_array_elements(Item.data["evidence"])
            .table_valued(column("value", JSONB))
            .alias("ev")
        )
        conds.append(
            func.lower(Item.data["owner"].astext).in_(people)
            | func.lower(Item.data["requester"].astext).in_(people)
            | exists(
                select(1)
                .select_from(ev)
                .where(func.lower(ev.c.value["speaker"].astext).in_(people))
            )
        )
    return select(Item.id).join(Meeting, Meeting.id == Item.meeting_id).where(and_(*conds))


def _chunk_stmt(org_id: str, f: SearchFilters) -> Select[Any]:
    conds: list[ColumnElement[bool]] = [
        TranscriptChunk.org_id == org_id,
        TranscriptChunk.embedding.is_not(None),
        *_meeting_conds(org_id, f),
    ]
    people = _people(f)
    if people:
        sp = (
            func.jsonb_array_elements_text(TranscriptChunk.speakers)
            .table_valued("value")
            .alias("sp")
        )
        conds.append(
            exists(select(1).select_from(sp).where(func.lower(sp.c.value).in_(people)))
        )
    return (
        select(TranscriptChunk.id)
        .join(Meeting, Meeting.id == TranscriptChunk.meeting_id)
        .where(and_(*conds))
    )


async def search_items_vector(
    session: AsyncSession,
    *,
    org_id: str,
    query_vec: list[float],
    filters: SearchFilters,
    limit: int = 20,
) -> list[str]:
    stmt = _item_stmt(org_id, filters).order_by(Item.embedding.cosine_distance(query_vec))
    return list((await session.scalars(stmt.limit(limit))).all())


async def search_items_keyword(
    session: AsyncSession,
    *,
    org_id: str,
    query: str,
    filters: SearchFilters,
    limit: int = 20,
) -> list[str]:
    score = func.word_similarity(query.lower(), func.lower(Item.search_text))
    stmt = _item_stmt(org_id, filters).where(score > KEYWORD_THRESHOLD).order_by(score.desc())
    return list((await session.scalars(stmt.limit(limit))).all())


async def search_chunks_vector(
    session: AsyncSession,
    *,
    org_id: str,
    query_vec: list[float],
    filters: SearchFilters,
    limit: int = 20,
) -> list[str]:
    stmt = _chunk_stmt(org_id, filters).order_by(
        TranscriptChunk.embedding.cosine_distance(query_vec)
    )
    return list((await session.scalars(stmt.limit(limit))).all())


async def search_chunks_keyword(
    session: AsyncSession,
    *,
    org_id: str,
    query: str,
    filters: SearchFilters,
    limit: int = 20,
) -> list[str]:
    score = func.word_similarity(query.lower(), func.lower(TranscriptChunk.text))
    stmt = _chunk_stmt(org_id, filters).where(score > KEYWORD_THRESHOLD).order_by(score.desc())
    return list((await session.scalars(stmt.limit(limit))).all())


async def hybrid_search(
    session: AsyncSession,
    *,
    org_id: str,
    query: str,
    query_vec: list[float],
    filters: SearchFilters,
) -> list[Hit]:
    iv = await search_items_vector(session, org_id=org_id, query_vec=query_vec, filters=filters)
    ik = await search_items_keyword(session, org_id=org_id, query=query, filters=filters)
    cv = await search_chunks_vector(session, org_id=org_id, query_vec=query_vec, filters=filters)
    ck = await search_chunks_keyword(session, org_id=org_id, query=query, filters=filters)
    fused = rrf_fuse(
        [
            [f"item:{i}" for i in iv],
            [f"item:{i}" for i in ik],
            [f"chunk:{i}" for i in cv],
            [f"chunk:{i}" for i in ck],
        ]
    )
    pairs = [key.partition(":") for key in fused]
    items = await load_items(session, org_id=org_id, ids=[p[2] for p in pairs if p[0] == "item"])
    chunks = await load_chunks(session, org_id=org_id, ids=[p[2] for p in pairs if p[0] == "chunk"])
    hits: list[Hit] = []
    for kind, _, rid in pairs:
        if kind == "item" and rid in items:
            hits.append(Hit("item", rid, items[rid].meeting_id))
        elif kind == "chunk" and rid in chunks:
            hits.append(Hit("chunk", rid, chunks[rid].meeting_id))
    return hits


async def load_items(session: AsyncSession, *, org_id: str, ids: list[str]) -> dict[str, Item]:
    if not ids:
        return {}
    stmt = (
        select(Item)
        .join(Meeting, Meeting.id == Item.meeting_id)
        .where(
            Item.org_id == org_id,
            Item.id.in_(ids),
            Item.review_state.in_(("approved", "edited")),
            Meeting.org_id == org_id,
            Meeting.status == "published",
        )
    )
    return {r.id: r for r in await session.scalars(stmt)}


async def load_chunks(
    session: AsyncSession, *, org_id: str, ids: list[str]
) -> dict[str, TranscriptChunk]:
    if not ids:
        return {}
    stmt = (
        select(TranscriptChunk)
        .join(Meeting, Meeting.id == TranscriptChunk.meeting_id)
        .where(
            TranscriptChunk.org_id == org_id,
            TranscriptChunk.id.in_(ids),
            Meeting.org_id == org_id,
            Meeting.status == "published",
        )
    )
    return {r.id: r for r in await session.scalars(stmt)}


async def meetings_by_id(
    session: AsyncSession, *, org_id: str, ids: list[str]
) -> dict[str, Meeting]:
    if not ids:
        return {}
    stmt = select(Meeting).where(
        Meeting.org_id == org_id, Meeting.status == "published", Meeting.id.in_(ids)
    )
    return {r.id: r for r in await session.scalars(stmt)}


async def org_projects(session: AsyncSession, *, org_id: str) -> list[str]:
    stmt = (
        select(Meeting.project)
        .where(
            Meeting.org_id == org_id,
            Meeting.status == "published",
            Meeting.project.is_not(None),
        )
        .distinct()
        .order_by(Meeting.project)
    )
    return [p for p in (await session.scalars(stmt)).all() if p is not None]


async def decisions_for_meetings(
    session: AsyncSession, *, org_id: str, meeting_ids: list[str]
) -> list[Item]:
    if not meeting_ids:
        return []
    stmt = (
        select(Item)
        .join(Meeting, Meeting.id == Item.meeting_id)
        .where(
            Item.org_id == org_id,
            Item.meeting_id.in_(meeting_ids),
            Item.type == "decision",
            Item.review_state.in_(("approved", "edited")),
            Meeting.org_id == org_id,
            Meeting.status == "published",
        )
        .order_by(Item.meeting_id, Item.position)
    )
    return list((await session.scalars(stmt)).all())


async def has_published(session: AsyncSession, *, org_id: str) -> bool:
    stmt = select(Meeting.id).where(Meeting.org_id == org_id, Meeting.status == "published").limit(1)
    return (await session.scalar(stmt)) is not None
