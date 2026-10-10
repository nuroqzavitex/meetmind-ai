import json
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.api_helpers import MAX_UPLOAD, FakeQueue, auth

from app.core.config import STALE_JOB_SECONDS
from app.models import Job
from app.repositories import jobs as jobs_repo
from app.repositories import meetings as meetings_repo

pytestmark = pytest.mark.db

CTX = {"title": "Chốt CSDL", "meeting_date": "2026-10-01", "project": "pay", "organizer": "Lan"}


async def upload(
    client: httpx.AsyncClient,
    data: bytes,
    *,
    filename: str = "t.txt",
    context: str | None = None,
    headers: dict[str, str] | None = None,
    **ctx_over: Any,
) -> httpx.Response:
    ctx = context if context is not None else json.dumps({**CTX, **ctx_over})
    return await client.post(
        "/meetings",
        files={"file": (filename, data)},
        data={"context": ctx},
        headers=auth() if headers is None else headers,
    )


async def test_upload_creates_meeting_and_enqueues(
    client: httpx.AsyncClient, queue: FakeQueue, transcript_bytes: bytes
) -> None:
    r = await upload(client, transcript_bytes)
    assert r.status_code == 201
    body = r.json()
    mid, jid = body["meeting_id"], body["job_id"]
    assert queue.calls == [("analyze", "org_a", mid, jid)]

    job = await client.get(f"/jobs/{jid}", headers=auth())
    assert job.status_code == 200 and job.json()["status"] == "queued"

    m = (await client.get(f"/meetings/{mid}", headers=auth())).json()
    assert m["status"] == "analyzing"
    assert m["active_job_id"] == jid
    assert m["utterances"] == []
    assert m["context"]["meeting_id"] == mid


@pytest.mark.parametrize(
    ("kwargs", "status", "code"),
    [
        ({"data": b""}, 422, "transcript_parse_error"),
        ({"data": b"\xff\xfe\x00garbage", "filename": "x.txt"}, 422, "transcript_parse_error"),
        ({"data": b"hello", "filename": "notes.pdf"}, 422, "transcript_parse_error"),
        ({"data": b"a" * (MAX_UPLOAD + 1)}, 413, "file_too_large"),
        ({"data": b"x", "context": "{not json"}, 422, "validation_error"),
        (
            {"data": b"x", "context": json.dumps({"meeting_date": "2026-10-01"})},
            422,
            "validation_error",
        ),
    ],
)
async def test_bad_uploads_rejected(
    client: httpx.AsyncClient,
    queue: FakeQueue,
    transcript_bytes: bytes,
    kwargs: dict[str, Any],
    status: int,
    code: str,
) -> None:
    kwargs = dict(kwargs)
    kwargs.setdefault("filename", "t.txt")
    r = await upload(client, kwargs.pop("data"), **kwargs)
    assert r.status_code == status
    assert r.json()["error"]["code"] == code
    assert (await client.get("/meetings", headers=auth())).json() == []
    assert queue.calls == []


async def test_requires_auth_and_org(client: httpx.AsyncClient, transcript_bytes: bytes) -> None:
    assert (await upload(client, transcript_bytes, headers={})).status_code == 401
    assert (await client.get("/meetings")).status_code == 401
    r = await client.get("/meetings", headers=auth(org=None))
    assert r.status_code == 403


async def test_list_filters_by_project(client: httpx.AsyncClient, transcript_bytes: bytes) -> None:
    await upload(client, transcript_bytes, project="pay")
    await upload(client, transcript_bytes, project="crm")
    r = await client.get("/meetings", params={"project": "pay"}, headers=auth())
    assert [m["project"] for m in r.json()] == ["pay"]
    assert len((await client.get("/meetings", headers=auth())).json()) == 2
    assert (await client.get("/meetings", headers=auth(org="org_b"))).json() == []


async def test_cross_org_is_404(client: httpx.AsyncClient, transcript_bytes: bytes) -> None:
    body = (await upload(client, transcript_bytes)).json()
    other = auth(org="org_b")
    assert (await client.get(f"/meetings/{body['meeting_id']}", headers=other)).status_code == 404
    assert (await client.get(f"/jobs/{body['job_id']}", headers=other)).status_code == 404


async def test_reanalyze_only_when_failed(
    client: httpx.AsyncClient,
    queue: FakeQueue,
    transcript_bytes: bytes,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    body = (await upload(client, transcript_bytes)).json()
    mid = body["meeting_id"]
    r = await client.post(f"/meetings/{mid}/reanalyze", headers=auth())
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_failed"

    async with sessionmaker() as s:
        await meetings_repo.set_status(s, org_id="org_a", meeting_id=mid, status="failed")
        await s.commit()
    r = await client.post(f"/meetings/{mid}/reanalyze", headers=auth())
    assert r.status_code == 202
    new_job = r.json()["job_id"]
    assert new_job != body["job_id"]
    assert len(queue.calls) == 2 and queue.calls[1] == ("analyze", "org_a", mid, new_job)


async def test_enqueue_failure_marks_failed_and_503(
    client: httpx.AsyncClient,
    queue: FakeQueue,
    transcript_bytes: bytes,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async def boom(*_: Any, **__: Any) -> None:
        raise ConnectionError("redis down")

    queue.enqueue = boom  # type: ignore[method-assign]
    r = await upload(client, transcript_bytes)
    assert r.status_code == 503 and r.json()["error"]["code"] == "queue_unavailable"
    listed = (await client.get("/meetings", headers=auth())).json()
    assert [m["status"] for m in listed] == ["failed"]
    async with sessionmaker() as s:
        job = await jobs_repo.get(s, org_id="org_a", job_id=await _only_job_id(s))
    assert job is not None
    assert job.status == "failed" and job.error == "Không đưa được job vào hàng đợi"


async def _only_job_id(s: AsyncSession) -> str:
    from sqlalchemy import select

    from app.models import Job

    return str(await s.scalar(select(Job.id)))


async def test_reanalyze_cross_org_is_404(
    client: httpx.AsyncClient, transcript_bytes: bytes
) -> None:
    body = (await upload(client, transcript_bytes)).json()
    r = await client.post(f"/meetings/{body['meeting_id']}/reanalyze", headers=auth(org="org_b"))
    assert r.status_code == 404


async def test_reanalyze_stale_analyzing_meeting(
    client: httpx.AsyncClient,
    queue: FakeQueue,
    transcript_bytes: bytes,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    body = (await upload(client, transcript_bytes)).json()
    mid, old_job = body["meeting_id"], body["job_id"]
    fresh = await client.post(f"/meetings/{mid}/reanalyze", headers=auth())
    assert fresh.status_code == 409 and fresh.json()["error"]["code"] == "not_failed"

    async with sessionmaker() as s:
        await s.execute(
            update(Job)
            .where(Job.id == old_job)
            .values(updated_at=func.now() - timedelta(seconds=STALE_JOB_SECONDS + 60))
        )
        await s.commit()
    r = await client.post(f"/meetings/{mid}/reanalyze", headers=auth())
    assert r.status_code == 202 and r.json()["job_id"] != old_job
    assert len(queue.calls) == 2
    async with sessionmaker() as s:
        old = await jobs_repo.get(s, org_id="org_a", job_id=old_job)
        assert old is not None and old.status == "failed"
    detail = (await client.get(f"/meetings/{mid}", headers=auth())).json()
    assert detail["status"] == "analyzing" and detail["active_job_id"] == r.json()["job_id"]
    again = await client.post(f"/meetings/{mid}/reanalyze", headers=auth())
    assert again.status_code == 409


async def test_failed_meeting_detail_exposes_latest_job(
    client: httpx.AsyncClient,
    transcript_bytes: bytes,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    body = (await upload(client, transcript_bytes)).json()
    mid = body["meeting_id"]
    async with sessionmaker() as s:
        await jobs_repo.update(
            s, org_id="org_a", job_id=body["job_id"], status="failed", step="topics", error="boom"
        )
        await meetings_repo.set_status(s, org_id="org_a", meeting_id=mid, status="failed")
        await s.commit()
    detail = (await client.get(f"/meetings/{mid}", headers=auth())).json()
    assert detail["active_job_id"] is None
    latest = detail["latest_job"]
    assert latest["status"] == "failed" and latest["step"] == "topics"
    assert latest["error"] == "boom" and latest["id"] == body["job_id"]


async def test_enqueue_failure_survives_failing_cleanup(
    client: httpx.AsyncClient,
    queue: FakeQueue,
    transcript_bytes: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(*_: Any, **__: Any) -> None:
        raise ConnectionError("redis down")

    async def boom_update(*_: Any, **__: Any) -> None:
        raise ConnectionError("db down")

    queue.enqueue = boom  # type: ignore[method-assign]
    monkeypatch.setattr(jobs_repo, "update", boom_update)
    r = await upload(client, transcript_bytes)
    assert r.status_code == 503 and r.json()["error"]["code"] == "queue_unavailable"


@pytest.mark.parametrize(
    "over",
    [
        {"project": "x" * 201},
        {"organizer": "x" * 201},
        {"participants": [{"name": "a"}] * 101},
        {"glossary": ["g"] * 501},
    ],
)
async def test_context_length_caps(
    client: httpx.AsyncClient, transcript_bytes: bytes, over: dict[str, Any]
) -> None:
    r = await upload(client, transcript_bytes, **over)
    assert r.status_code == 422
