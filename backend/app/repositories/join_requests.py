from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JoinRequest, OrgSettings


async def org_for_code(session: AsyncSession, *, code: str) -> str | None:
    return await session.scalar(select(OrgSettings.org_id).where(OrgSettings.join_code == code))


async def code_taken(session: AsyncSession, *, code: str) -> bool:
    return await org_for_code(session, code=code) is not None


async def pending_for(session: AsyncSession, *, org_id: str, user_id: str) -> JoinRequest | None:
    return await session.scalar(
        select(JoinRequest).where(
            JoinRequest.org_id == org_id,
            JoinRequest.user_id == user_id,
            JoinRequest.status == "pending",
        )
    )


async def count_pending_by_user(session: AsyncSession, *, user_id: str) -> int:
    n = await session.scalar(
        select(func.count())
        .select_from(JoinRequest)
        .where(JoinRequest.user_id == user_id, JoinRequest.status == "pending")
    )
    return int(n or 0)


async def list_by_user(session: AsyncSession, *, user_id: str) -> list[JoinRequest]:
    stmt = (
        select(JoinRequest)
        .where(JoinRequest.user_id == user_id)
        .order_by(JoinRequest.created_at.desc())
        .limit(20)
    )
    return list((await session.scalars(stmt)).all())


async def get_for_user(session: AsyncSession, *, user_id: str, request_id: str) -> JoinRequest | None:
    return await session.scalar(
        select(JoinRequest).where(JoinRequest.id == request_id, JoinRequest.user_id == user_id)
    )


async def list_pending(session: AsyncSession, *, org_id: str) -> list[JoinRequest]:
    stmt = (
        select(JoinRequest)
        .where(JoinRequest.org_id == org_id, JoinRequest.status == "pending")
        .order_by(JoinRequest.created_at)
    )
    return list((await session.scalars(stmt)).all())


async def get(session: AsyncSession, *, org_id: str, request_id: str) -> JoinRequest | None:
    return await session.scalar(
        select(JoinRequest).where(JoinRequest.id == request_id, JoinRequest.org_id == org_id)
    )
