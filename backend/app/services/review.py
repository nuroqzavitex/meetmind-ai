"""Review use-cases: list items/topics, approve/edit/reject, bulk-approve clean items."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.validate import REQUIRED_FLAGS
from app.ai.domain.enums import ItemType, ReviewState
from app.ai.domain.models import MeetingItem
from app.ai.domain.state_machine import Topic
from app.core.auth import Principal
from app.core.errors import Conflict, NotFound, Unprocessable
from app.repositories import items as items_repo
from app.repositories import meetings
from app.schemas.items import ItemAction, ItemEventOut

_NOT_FOUND_MEETING = "Không tìm thấy cuộc họp"
_NOT_FOUND_ITEM = "Không tìm thấy mục"


async def _require_meeting(session: AsyncSession, principal: Principal, meeting_id: str) -> str:
    row = await meetings.get(session, org_id=principal.org_id, meeting_id=meeting_id)
    if row is None:
        raise NotFound(_NOT_FOUND_MEETING)
    return row.status


async def _require_in_review(session: AsyncSession, principal: Principal, meeting_id: str) -> None:
    if await _require_meeting(session, principal, meeting_id) != "in_review":
        raise Conflict("Cuộc họp không ở trạng thái duyệt", "not_in_review")


def _group(item: MeetingItem) -> int:
    if "low_confidence" in item.flags:
        return 0
    return 1 if item.flags else 2


async def list_items(
    session: AsyncSession, *, principal: Principal, meeting_id: str
) -> list[MeetingItem]:
    await _require_meeting(session, principal, meeting_id)
    rows = await items_repo.list_for_meeting(
        session, org_id=principal.org_id, meeting_id=meeting_id
    )
    models = [items_repo.to_model(r) for r in rows]
    return sorted(models, key=_group)  # stable: keeps position order inside each group


async def list_topics(
    session: AsyncSession, *, principal: Principal, meeting_id: str
) -> list[Topic]:
    await _require_meeting(session, principal, meeting_id)
    return await meetings.get_topics(session, org_id=principal.org_id, meeting_id=meeting_id)


def _recompute_flags(item: MeetingItem) -> list[str]:
    required = REQUIRED_FLAGS.get(item.type, [])
    owned = {flag for _, flag in required}
    flags = [f for f in item.flags if f not in owned]
    flags.extend(flag for attr, flag in required if not getattr(item, attr))
    return flags


def _edit(item: MeetingItem, action: ItemAction) -> MeetingItem:
    if action.patch is None:
        raise Unprocessable("Thiếu nội dung chỉnh sửa", "patch_required")
    changes = action.patch.model_dump(exclude_unset=True)
    changed = any(k in changes and changes[k] != getattr(item, k) for k in ("content", "status"))
    if item.type == ItemType.DECISION and changed and not (action.reason or "").strip():
        raise Unprocessable("Cần lý do khi đổi quyết định", "reason_required")
    try:
        edited = MeetingItem.model_validate(item.model_copy(update=changes).model_dump())
    except ValueError as exc:
        raise Unprocessable(str(exc), "validation_error") from exc
    return edited.model_copy(
        update={"flags": _recompute_flags(edited), "review_state": ReviewState.EDITED}
    )


async def act_on_item(
    session: AsyncSession, *, principal: Principal, item_id: str, action: ItemAction
) -> MeetingItem:
    row = await items_repo.get(session, org_id=principal.org_id, item_id=item_id)
    if row is None:
        raise NotFound(_NOT_FOUND_ITEM)
    await _require_in_review(session, principal, row.meeting_id)
    before = items_repo.to_model(row)
    if action.action == "approve":
        after = before.model_copy(update={"review_state": ReviewState.APPROVED})
        event = "approved"
    elif action.action == "reject":
        after = before.model_copy(update={"review_state": ReviewState.REJECTED})
        event = "rejected"
    else:
        after = _edit(before, action)
        event = "edited"
    await items_repo.save(session, item=row, model=after)
    await items_repo.add_event(
        session,
        item=row,
        actor=principal,
        action=event,
        before=before.model_dump(mode="json"),
        after=after.model_dump(mode="json"),
        reason=action.reason,
    )
    await session.commit()
    return after


async def approve_clean(session: AsyncSession, *, principal: Principal, meeting_id: str) -> int:
    await _require_in_review(session, principal, meeting_id)
    rows = await items_repo.list_for_meeting(
        session, org_id=principal.org_id, meeting_id=meeting_id
    )
    count = 0
    for row in rows:
        model = items_repo.to_model(row)
        if model.review_state != ReviewState.PENDING or model.flags:
            continue
        after = model.model_copy(update={"review_state": ReviewState.APPROVED})
        await items_repo.save(session, item=row, model=after)
        await items_repo.add_event(
            session,
            item=row,
            actor=principal,
            action="approved",
            before=model.model_dump(mode="json"),
            after=after.model_dump(mode="json"),
        )
        count += 1
    await session.commit()
    return count


async def list_events(
    session: AsyncSession, *, principal: Principal, item_id: str
) -> list[ItemEventOut]:
    row = await items_repo.get(session, org_id=principal.org_id, item_id=item_id)
    if row is None:
        raise NotFound(_NOT_FOUND_ITEM)
    events = await items_repo.events(session, org_id=principal.org_id, item_id=item_id)
    return [ItemEventOut.model_validate(e) for e in events]
