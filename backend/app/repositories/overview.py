from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item, Meeting

PUBLISHED = "published"
KEPT = ("approved", "edited")


async def published_items(
    session: AsyncSession, *, org_id: str, project: str | None = None
) -> list[tuple[Meeting, Item]]:
    """Reviewed items of the org's published meetings, oldest meeting first."""
    stmt = (
        select(Meeting, Item)
        .join(Item, Item.meeting_id == Meeting.id)
        .where(
            Meeting.org_id == org_id,
            Item.org_id == org_id,
            Meeting.status == PUBLISHED,
            Item.review_state.in_(KEPT),
        )
        .order_by(Meeting.meeting_date, Meeting.created_at, Item.position)
    )
    if project:
        stmt = stmt.where(Meeting.project == project)
    return [(m, i) for m, i in (await session.execute(stmt)).all()]


async def projects(session: AsyncSession, *, org_id: str) -> list[str]:
    stmt = (
        select(Meeting.project)
        .where(Meeting.org_id == org_id, Meeting.status == PUBLISHED, Meeting.project.is_not(None))
        .distinct()
        .order_by(Meeting.project)
    )
    return [p for p in (await session.scalars(stmt)).all() if p]
