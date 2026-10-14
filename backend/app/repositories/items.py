from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.domain.enums import ItemStatus, ItemType, ReviewState
from app.ai.domain.models import MeetingItem
from app.core.auth import Principal
from app.models import Item, ItemEvent, Meeting


def to_model(item: Item) -> MeetingItem:
    return MeetingItem.model_validate(item.data)


async def replace_for_meeting(
    session: AsyncSession, *, org_id: str, meeting_id: str, items: list[MeetingItem]
) -> list[Item]:
    owned = await session.scalar(
        select(Meeting.id).where(Meeting.id == meeting_id, Meeting.org_id == org_id)
    )
    if owned is None:
        return []
    await session.execute(delete(Item).where(Item.org_id == org_id, Item.meeting_id == meeting_id))
    rows = [
        Item(
            id=m.id,
            org_id=org_id,
            meeting_id=meeting_id,
            type=m.type.value,
            status=m.status.value,
            review_state=m.review_state.value,
            data=m.model_dump(mode="json"),
            position=i,
        )
        for i, m in enumerate(items)
    ]
    session.add_all(rows)
    await session.flush()
    return rows


async def list_for_meeting(session: AsyncSession, *, org_id: str, meeting_id: str) -> list[Item]:
    stmt = (
        select(Item)
        .where(Item.org_id == org_id, Item.meeting_id == meeting_id)
        .order_by(Item.position)
    )
    return list((await session.scalars(stmt)).all())


async def get(session: AsyncSession, *, org_id: str, item_id: str) -> Item | None:
    return await session.scalar(select(Item).where(Item.id == item_id, Item.org_id == org_id))


async def save(session: AsyncSession, *, item: Item, model: MeetingItem) -> None:
    item.data = model.model_dump(mode="json")
    item.type = model.type.value
    item.status = model.status.value
    item.review_state = model.review_state.value
    item.updated_at = datetime.now(UTC)
    await session.flush()


async def add_event(
    session: AsyncSession,
    *,
    item: Item,
    actor: Principal,
    action: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> ItemEvent:
    event = ItemEvent(
        item_id=item.id,
        actor_id=actor.user_id,
        actor_name=actor.name,
        action=action,
        before=before,
        after=after,
        reason=reason,
    )
    session.add(event)
    await session.flush()
    return event


async def events(session: AsyncSession, *, org_id: str, item_id: str) -> list[ItemEvent]:
    stmt = (
        select(ItemEvent)
        .join(Item, Item.id == ItemEvent.item_id)
        .where(Item.org_id == org_id, ItemEvent.item_id == item_id)
        .order_by(ItemEvent.pk)
    )
    return list((await session.scalars(stmt)).all())


async def due_action_items(
    session: AsyncSession, *, org_id: str, start: date, end: date
) -> list[tuple[Item, Meeting]]:
    """Kept action items of published meetings with `start <= due_date <= end`."""
    due = Item.data["due_date"].astext  # ISO dates compare correctly as strings
    stmt = (
        select(Item, Meeting)
        .join(Meeting, Meeting.id == Item.meeting_id)
        .where(
            Item.org_id == org_id,
            Meeting.org_id == org_id,
            Meeting.status == "published",
            Item.type == ItemType.ACTION_ITEM.value,
            Item.review_state.in_([ReviewState.APPROVED.value, ReviewState.EDITED.value]),
            Item.status != ItemStatus.SUPERSEDED.value,
            due >= start.isoformat(),
            due <= end.isoformat(),
        )
        .order_by(due, Item.position)
    )
    return [(i, m) for i, m in (await session.execute(stmt)).all()]
