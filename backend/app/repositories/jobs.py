import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, Meeting

_IMMUTABLE = {"id", "org_id", "meeting_id", "kind", "created_at", "updated_at"}


async def create(session: AsyncSession, *, org_id: str, meeting_id: str, kind: str) -> Job:
    owned = await session.scalar(
        select(Meeting.id).where(Meeting.id == meeting_id, Meeting.org_id == org_id)
    )
    if owned is None:
        raise LookupError(f"Meeting {meeting_id} not found in org")
    job = Job(
        id=str(uuid.uuid4()),
        org_id=org_id,
        meeting_id=meeting_id,
        kind=kind,
        status="queued",
        progress=0.0,
    )
    session.add(job)
    await session.flush()
    return job


async def get(session: AsyncSession, *, org_id: str, job_id: str) -> Job | None:
    return await session.scalar(select(Job).where(Job.id == job_id, Job.org_id == org_id))


async def update(session: AsyncSession, *, org_id: str, job_id: str, **fields: Any) -> None:
    unknown = set(fields) - (set(Job.__table__.columns.keys()) - _IMMUTABLE)
    if unknown:
        raise AttributeError(f"Unknown job field(s): {', '.join(sorted(unknown))}")
    await session.execute(
        sa_update(Job)
        .where(Job.id == job_id, Job.org_id == org_id)
        .values(**fields, updated_at=func.now())
    )


async def active_for_meeting(
    session: AsyncSession, *, org_id: str, meeting_id: str, kind: str = "analyze"
) -> Job | None:
    return await session.scalar(
        select(Job)
        .where(
            Job.org_id == org_id,
            Job.meeting_id == meeting_id,
            Job.kind == kind,
            Job.status.in_(("queued", "running")),
        )
        .order_by(Job.created_at.desc())
        .limit(1)
    )


async def latest_for_meeting(
    session: AsyncSession, *, org_id: str, meeting_id: str, kind: str = "analyze"
) -> Job | None:
    return await session.scalar(
        select(Job)
        .where(Job.org_id == org_id, Job.meeting_id == meeting_id, Job.kind == kind)
        .order_by(Job.created_at.desc())
        .limit(1)
    )


async def fail_stale(
    session: AsyncSession, *, org_id: str, meeting_id: str, older_than_seconds: int, error: str
) -> int:
    """Fail queued/running jobs not updated for `older_than_seconds`; returns how many."""
    result = await session.execute(
        sa_update(Job)
        .where(
            Job.org_id == org_id,
            Job.meeting_id == meeting_id,
            Job.status.in_(("queued", "running")),
            Job.updated_at < func.now() - timedelta(seconds=older_than_seconds),
        )
        .values(status="failed", error=error, updated_at=func.now())
    )
    return int(result.rowcount)  # type: ignore[attr-defined]
