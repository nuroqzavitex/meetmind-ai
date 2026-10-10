"""Job queue abstraction; production implementation is backed by arq/Redis."""

from typing import Protocol

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import Request


class JobQueue(Protocol):
    async def enqueue(self, kind: str, *, org_id: str, meeting_id: str, job_id: str) -> None: ...


class ArqQueue:
    """Wraps an ArqRedis pool created lazily on first use."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._pool: ArqRedis | None = None

    async def _get_pool(self) -> ArqRedis:
        if self._pool is None:
            redis = RedisSettings.from_dsn(self._redis_url)
            redis.conn_retries = 0  # fail fast so the API can answer 503 instead of hanging
            redis.conn_timeout = 2
            self._pool = await create_pool(redis)
        return self._pool

    async def enqueue(self, kind: str, *, org_id: str, meeting_id: str, job_id: str) -> None:
        pool = await self._get_pool()
        await pool.enqueue_job(
            kind, org_id=org_id, meeting_id=meeting_id, job_id=job_id, _job_id=job_id
        )


def get_queue(request: Request) -> JobQueue:
    queue: JobQueue = request.app.state.queue
    return queue
