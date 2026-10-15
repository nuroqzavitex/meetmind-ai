"""Join an organization with its join code; org admins approve or reject."""

import logging
import re
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, User, require_admin
from app.core.clerk_api import ClerkAPI, ClerkError, ClerkUnavailable
from app.core.errors import (
    BadGateway,
    Conflict,
    NotFound,
    ServiceUnavailable,
    TooManyRequests,
)
from app.models import JoinRequest
from app.notify.discord import DiscordClient, DiscordError
from app.notify.messages import join_request_message
from app.repositories import join_requests as repo
from app.repositories import org_settings as settings_repo
from app.schemas.join_requests import JoinCodeOut, JoinRequestOut

logger = logging.getLogger(__name__)

# No 0/O, 1/I/L: codes are read aloud and typed by hand.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
MAX_PENDING_PER_USER = 5
_NOT_FOUND = "Không tìm thấy yêu cầu"
_INVALID_CODE = "Mã tham gia không đúng hoặc đã được đổi"


def new_code() -> str:
    body = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"MM-{body[:4]}-{body[4:]}"


def normalize_code(raw: str) -> str | None:
    """Accept "mm-7k3q-x9p2", "7K3QX9P2", "MM 7K3Q X9P2"; None when it cannot be a code."""
    s = re.sub(r"[^A-Z0-9]", "", raw.upper())
    if len(s) == 10 and s.startswith("MM"):
        s = s[2:]
    if len(s) != 8 or any(c not in ALPHABET for c in s):
        return None
    return f"MM-{s[:4]}-{s[4:]}"


def _clerk_failure(exc: ClerkError) -> Exception:
    if isinstance(exc, ClerkUnavailable):
        return ServiceUnavailable(str(exc), "clerk_unavailable")
    return BadGateway(str(exc), "clerk_error")


async def get_join_code(session: AsyncSession, *, principal: Principal) -> JoinCodeOut:
    require_admin(principal)
    row = await settings_repo.get_or_create(session, org_id=principal.org_id)
    if row.join_code is None:
        row.join_code = await _unused_code(session)
        await session.commit()
    return JoinCodeOut(code=row.join_code)


async def rotate_join_code(session: AsyncSession, *, principal: Principal) -> JoinCodeOut:
    require_admin(principal)
    row = await settings_repo.get_or_create(session, org_id=principal.org_id)
    row.join_code = await _unused_code(session)
    await session.commit()
    return JoinCodeOut(code=row.join_code)


async def _unused_code(session: AsyncSession) -> str:
    while True:  # 31^8 codes: a collision is practically impossible, but cheap to rule out
        code = new_code()
        if not await repo.code_taken(session, code=code):
            return code


async def create(
    session: AsyncSession, clerk: ClerkAPI, *, user: User, raw_code: str
) -> tuple[JoinRequestOut, str | None]:
    """Create a pending request. Returns it with the org's Discord webhook (None if not set)."""
    code = normalize_code(raw_code)
    org_id = await repo.org_for_code(session, code=code) if code else None
    if org_id is None:
        raise NotFound(_INVALID_CODE, "invalid_code")
    if user.org_id == org_id:
        raise Conflict("Bạn đã là thành viên của tổ chức này", "already_member")
    if await repo.pending_for(session, org_id=org_id, user_id=user.user_id):
        raise Conflict("Bạn đã gửi yêu cầu vào tổ chức này, đang chờ duyệt", "already_requested")
    if await repo.count_pending_by_user(session, user_id=user.user_id) >= MAX_PENDING_PER_USER:
        raise TooManyRequests(
            f"Bạn đang có {MAX_PENDING_PER_USER} yêu cầu chờ duyệt, hãy huỷ bớt", "too_many_requests"
        )
    try:
        profile = await clerk.get_user(user.user_id)
        org_name = await clerk.get_org_name(org_id)
    except ClerkError as exc:
        raise _clerk_failure(exc) from exc
    row = JoinRequest(
        id=str(uuid.uuid4()),
        org_id=org_id,
        org_name=org_name,
        user_id=user.user_id,
        user_name=profile.name,
        user_email=profile.email,
        status="pending",
        created_at=datetime.now(UTC),
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as exc:  # a concurrent request for the same org won the race
        await session.rollback()
        raise Conflict(
            "Bạn đã gửi yêu cầu vào tổ chức này, đang chờ duyệt", "already_requested"
        ) from exc
    settings = await settings_repo.get(session, org_id=org_id)
    return JoinRequestOut.model_validate(row), settings.discord_webhook_url if settings else None


async def list_mine(session: AsyncSession, clerk: ClerkAPI, *, user: User) -> list[JoinRequestOut]:
    """The latest request per org. An approved one is dropped once the user has left that org."""
    latest: dict[str, JoinRequest] = {}
    for r in await repo.list_by_user(session, user_id=user.user_id):  # newest first
        latest.setdefault(r.org_id, r)
    rows = list(latest.values())
    if any(r.status == "approved" for r in rows):
        try:
            orgs: set[str] | None = await clerk.member_org_ids(user.user_id)
        except ClerkError:  # keep the page usable; "Vào tổ chức" explains a failed switch
            logger.warning("Could not read Clerk memberships for %s", user.user_id)
            orgs = None
        if orgs is not None:
            rows = [r for r in rows if r.status != "approved" or r.org_id in orgs]
    out = []
    for r in rows:
        item = JoinRequestOut.model_validate(r)
        if r.status == "approved":
            settings = await settings_repo.get(session, org_id=r.org_id)
            item.discord_invite_url = settings.discord_invite_url if settings else None
        out.append(item)
    return out


async def cancel(session: AsyncSession, *, user: User, request_id: str) -> None:
    row = await repo.get_for_user(session, user_id=user.user_id, request_id=request_id)
    if row is None:
        raise NotFound(_NOT_FOUND)
    if row.status != "pending":
        raise Conflict("Yêu cầu đã được xử lý", "not_pending")
    row.status, row.decided_at = "cancelled", datetime.now(UTC)
    await session.commit()


async def list_pending(session: AsyncSession, *, principal: Principal) -> list[JoinRequestOut]:
    require_admin(principal)
    rows = await repo.list_pending(session, org_id=principal.org_id)
    return [JoinRequestOut.model_validate(r) for r in rows]


async def decide(
    session: AsyncSession, clerk: ClerkAPI, *, principal: Principal, request_id: str, approve: bool
) -> JoinRequestOut:
    require_admin(principal)
    row = await repo.get(session, org_id=principal.org_id, request_id=request_id)
    if row is None:
        raise NotFound(_NOT_FOUND)
    if row.status != "pending":
        raise Conflict("Yêu cầu đã được xử lý", "not_pending")
    if approve:
        try:
            await clerk.add_member(principal.org_id, row.user_id)
        except ClerkError as exc:
            raise _clerk_failure(exc) from exc
    row.status = "approved" if approve else "rejected"
    row.decided_at, row.decided_by = datetime.now(UTC), principal.user_id
    await session.commit()
    return JoinRequestOut.model_validate(row)


async def notify_discord(
    discord: DiscordClient, webhook_url: str, request: JoinRequestOut, app_url: str
) -> None:
    """Background task after a new request; Discord failures are only logged."""
    try:
        await discord.send(webhook_url, join_request_message(request, f"{app_url}/settings"))
    except DiscordError:
        logger.exception("Discord join-request notification failed for org %s", request.org_id)
