"""Publish, export, report and reopen use-cases."""

import json
import re
import unicodedata
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.domain.enums import ReviewState
from app.ai.domain.models import MeetingContext, MeetingItem
from app.core.auth import Principal
from app.core.errors import Conflict, NotFound
from app.models import Item, Meeting
from app.repositories import items as items_repo
from app.repositories import jobs, meetings
from app.schemas.meetings import MeetingSummary
from app.services.export import render_json, render_markdown

_NOT_FOUND_MEETING = "Không tìm thấy cuộc họp"
_NOT_FOUND_ITEM = "Không tìm thấy mục"
_NOT_IN_REVIEW = "Cuộc họp không ở trạng thái duyệt"
_NOT_PUBLISHED = "Cuộc họp chưa được phát hành"


def _slug(title: str) -> str:
    text = unicodedata.normalize("NFKD", title.replace("đ", "d").replace("Đ", "D"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", "-", text.encode("ascii", "ignore").decode().lower())
    return text.strip("-") or "bien-ban"


async def _meeting(session: AsyncSession, principal: Principal, meeting_id: str) -> Meeting:
    row = await meetings.get(session, org_id=principal.org_id, meeting_id=meeting_id)
    if row is None:
        raise NotFound(_NOT_FOUND_MEETING)
    return row


async def publish(
    session: AsyncSession, *, principal: Principal, meeting_id: str
) -> MeetingSummary:
    org_id = principal.org_id
    row = await _meeting(session, principal, meeting_id)
    if row.status != "in_review":
        raise Conflict(_NOT_IN_REVIEW, "not_in_review")
    if await jobs.active_for_meeting(session, org_id=org_id, meeting_id=meeting_id):
        raise Conflict("Cuộc họp đang được phân tích", "job_running")
    rows = await items_repo.list_for_meeting(session, org_id=org_id, meeting_id=meeting_id)
    pending = sum(1 for r in rows if r.review_state == ReviewState.PENDING.value)
    if pending:
        raise Conflict(f"Còn {pending} mục chưa duyệt", "pending_items")
    moved = await meetings.transition_status(
        session,
        org_id=org_id,
        meeting_id=meeting_id,
        from_status="in_review",
        to_status="published",
    )
    if not moved:
        raise Conflict(_NOT_IN_REVIEW, "not_in_review")
    await meetings.set_status(
        session,
        org_id=org_id,
        meeting_id=meeting_id,
        status="published",
        published_at=datetime.now(UTC),
    )
    await session.commit()
    session.expire_all()
    row = await _meeting(session, principal, meeting_id)
    return MeetingSummary.model_validate(row)


async def export(
    session: AsyncSession, *, principal: Principal, meeting_id: str, fmt: Literal["md", "json"]
) -> tuple[str | bytes, str, str]:
    row = await _meeting(session, principal, meeting_id)
    if row.status != "published":
        raise Conflict(_NOT_PUBLISHED, "not_published")
    ctx = MeetingContext.model_validate(row.context)
    item_rows = await items_repo.list_for_meeting(
        session, org_id=principal.org_id, meeting_id=meeting_id
    )
    models = [items_repo.to_model(r) for r in item_rows]
    name = f"{_slug(row.title)}-{row.meeting_date.isoformat()}.{fmt}"
    if fmt == "md":
        return render_markdown(ctx, models, row.published_at), "text/markdown; charset=utf-8", name
    body = json.dumps(render_json(ctx, models), ensure_ascii=False, indent=2).encode("utf-8")
    return body, "application/json", name


async def _published_item(
    session: AsyncSession, principal: Principal, item_id: str
) -> tuple[Item, Meeting]:
    row = await items_repo.get(session, org_id=principal.org_id, item_id=item_id)
    if row is None:
        raise NotFound(_NOT_FOUND_ITEM)
    meeting = await _meeting(session, principal, row.meeting_id)
    if meeting.status != "published":
        raise Conflict(_NOT_PUBLISHED, "not_published")
    return row, meeting


async def report_item(
    session: AsyncSession, *, principal: Principal, item_id: str, reason: str
) -> None:
    row, _ = await _published_item(session, principal, item_id)
    await items_repo.add_event(session, item=row, actor=principal, action="reported", reason=reason)
    await session.commit()


async def reopen_item(
    session: AsyncSession, *, principal: Principal, item_id: str, reason: str | None
) -> MeetingItem:
    row, meeting = await _published_item(session, principal, item_id)
    before = items_repo.to_model(row)
    after = before.model_copy(update={"review_state": ReviewState.PENDING})
    moved = await meetings.transition_status(
        session,
        org_id=principal.org_id,
        meeting_id=meeting.id,
        from_status="published",
        to_status="in_review",
    )
    if not moved:
        raise Conflict(_NOT_PUBLISHED, "not_published")
    await items_repo.save(session, item=row, model=after)
    await items_repo.add_event(
        session,
        item=row,
        actor=principal,
        action="reopened",
        before=before.model_dump(mode="json"),
        after=after.model_dump(mode="json"),
        reason=reason,
    )
    await session.commit()
    return after
