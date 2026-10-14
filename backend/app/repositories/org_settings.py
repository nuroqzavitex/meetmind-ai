from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OrgSettings


async def get(session: AsyncSession, *, org_id: str) -> OrgSettings | None:
    return await session.get(OrgSettings, org_id)


async def get_or_create(session: AsyncSession, *, org_id: str) -> OrgSettings:
    row = await get(session, org_id=org_id)
    if row is None:
        row = OrgSettings(org_id=org_id, digest_enabled=False)
        session.add(row)
        await session.flush()
    return row


async def digest_targets(session: AsyncSession) -> list[OrgSettings]:
    """Orgs with a webhook and the daily digest turned on (the cron job spans all orgs)."""
    stmt = select(OrgSettings).where(
        OrgSettings.discord_webhook_url.is_not(None), OrgSettings.digest_enabled.is_(True)
    )
    return list((await session.scalars(stmt)).all())
