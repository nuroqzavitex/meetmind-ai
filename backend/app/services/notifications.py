"""Discord settings, the publish notification and the daily digest."""

import logging
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.domain.models import MeetingContext
from app.core.auth import Principal
from app.core.errors import BadGateway, Conflict, Unprocessable
from app.models import OrgSettings
from app.notify.discord import (
    DiscordClient,
    DiscordError,
    is_invite_url,
    is_webhook_url,
    webhook_hint,
)
from app.notify.messages import (
    OVERDUE_DAYS,
    UPCOMING_DAYS,
    DueTask,
    connected_message,
    digest_message,
    published_message,
    select_digest,
)
from app.repositories import items as items_repo
from app.repositories import meetings
from app.repositories import org_settings as settings_repo
from app.schemas.settings import DigestOut, DiscordSettingsIn, DiscordSettingsOut

logger = logging.getLogger(__name__)


def _out(row: OrgSettings | None) -> DiscordSettingsOut:
    url = row.discord_webhook_url if row else None
    return DiscordSettingsOut(
        configured=url is not None,
        webhook_hint=webhook_hint(url) if url else None,
        digest_enabled=bool(row and row.digest_enabled),
        invite_url=row.discord_invite_url if row else None,
    )


async def get_discord(session: AsyncSession, *, principal: Principal) -> DiscordSettingsOut:
    return _out(await settings_repo.get(session, org_id=principal.org_id))


async def save_discord(
    session: AsyncSession, *, principal: Principal, body: DiscordSettingsIn
) -> DiscordSettingsOut:
    row = await settings_repo.get_or_create(session, org_id=principal.org_id)
    if "webhook_url" in body.model_fields_set:
        url = (body.webhook_url or "").strip()
        if url and not is_webhook_url(url):
            raise Unprocessable(
                "URL webhook không hợp lệ. URL đúng có dạng"
                " https://discord.com/api/webhooks/<id>/<token>",
                "invalid_webhook",
            )
        row.discord_webhook_url = url or None
    if "invite_url" in body.model_fields_set:
        invite = (body.invite_url or "").strip()
        if invite and not is_invite_url(invite):
            raise Unprocessable(
                "Link mời Discord không hợp lệ. Link đúng có dạng https://discord.gg/<mã>",
                "invalid_invite",
            )
        row.discord_invite_url = invite or None
    row.digest_enabled = body.digest_enabled
    await session.commit()
    return _out(row)


async def send_test(
    session: AsyncSession, discord: DiscordClient, *, principal: Principal
) -> None:
    row = await settings_repo.get(session, org_id=principal.org_id)
    if row is None or row.discord_webhook_url is None:
        raise Conflict("Chưa cấu hình webhook Discord", "not_configured")
    try:
        await discord.send(row.discord_webhook_url, connected_message())
    except DiscordError as exc:
        raise BadGateway(str(exc), "discord_error") from exc


async def has_webhook(session: AsyncSession, *, org_id: str) -> bool:
    row = await settings_repo.get(session, org_id=org_id)
    return row is not None and row.discord_webhook_url is not None


async def notify_published(
    sm: async_sessionmaker[AsyncSession],
    discord: DiscordClient,
    *,
    org_id: str,
    meeting_id: str,
    app_url: str,
) -> None:
    """Worker job: post the published meeting's summary. Best-effort, errors are logged."""
    async with sm() as session:
        row = await settings_repo.get(session, org_id=org_id)
        meeting = await meetings.get(session, org_id=org_id, meeting_id=meeting_id)
        if row is None or row.discord_webhook_url is None or meeting is None:
            return
        if meeting.status != "published":
            return
        url = row.discord_webhook_url
        ctx = MeetingContext.model_validate(meeting.context)
        item_rows = await items_repo.list_for_meeting(
            session, org_id=org_id, meeting_id=meeting_id
        )
        items = [items_repo.to_model(r) for r in item_rows]
    payload = published_message(ctx, items, f"{app_url}/meetings/{meeting_id}/minutes")
    try:
        await discord.send(url, payload)
    except DiscordError:
        logger.exception("Discord notification failed for meeting %s", meeting_id)


async def run_digest(
    session: AsyncSession, discord: DiscordClient, *, today: date, app_url: str
) -> DigestOut:
    targets = await settings_repo.digest_targets(session)
    sent = failed = 0
    for target in targets:
        rows = await items_repo.due_action_items(
            session,
            org_id=target.org_id,
            start=today - timedelta(days=OVERDUE_DAYS),
            end=today + timedelta(days=UPCOMING_DAYS),
        )
        tasks = [DueTask(items_repo.to_model(i), m.id, m.title) for i, m in rows]
        digest = select_digest(tasks, today)
        if digest.empty() or target.discord_webhook_url is None:
            continue
        try:
            await discord.send(target.discord_webhook_url, digest_message(digest, today, app_url))
            sent += 1
        except DiscordError:
            logger.exception("Discord digest failed for org %s", target.org_id)
            failed += 1
    return DigestOut(orgs=len(targets), sent=sent, failed=failed)
