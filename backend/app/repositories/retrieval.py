from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.retrieval.indexing import ChunkSpec
from app.models import Item, TranscriptChunk


async def indexable_items(session: AsyncSession, *, org_id: str, meeting_id: str) -> list[Item]:
    stmt = (
        select(Item)
        .where(
            Item.org_id == org_id,
            Item.meeting_id == meeting_id,
            Item.review_state.in_(("approved", "edited")),
        )
        .order_by(Item.position)
    )
    return list((await session.scalars(stmt)).all())


async def set_item_index(
    session: AsyncSession, *, item: Item, search_text: str, embedding: list[float]
) -> None:
    item.search_text = search_text
    item.embedding = embedding
    item.indexed_at = datetime.now(UTC)
    await session.flush()


async def clear_item_index(session: AsyncSession, *, item: Item) -> None:
    item.search_text = None
    item.embedding = None
    item.indexed_at = None
    await session.flush()


async def has_chunks(session: AsyncSession, *, org_id: str, meeting_id: str) -> bool:
    found = await session.scalar(
        select(TranscriptChunk.id)
        .where(TranscriptChunk.org_id == org_id, TranscriptChunk.meeting_id == meeting_id)
        .limit(1)
    )
    return found is not None


async def replace_chunks(
    session: AsyncSession,
    *,
    org_id: str,
    meeting_id: str,
    chunks: list[ChunkSpec],
    embeddings: list[list[float]],
) -> None:
    await session.execute(
        delete(TranscriptChunk).where(
            TranscriptChunk.org_id == org_id, TranscriptChunk.meeting_id == meeting_id
        )
    )
    session.add_all(
        TranscriptChunk(
            id=f"{meeting_id}-c{n:03d}",
            org_id=org_id,
            meeting_id=meeting_id,
            seq=c.seq,
            start_ts=c.start_ts,
            end_ts=c.end_ts,
            first_utterance_id=c.first_utterance_id,
            speakers=c.speakers,
            text=c.text,
            embedding=e,
        )
        for n, (c, e) in enumerate(zip(chunks, embeddings, strict=True))
    )
    await session.flush()
