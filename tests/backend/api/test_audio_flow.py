import json

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.api_helpers import FakeQueue, auth

from app.ai.parsing import parse_transcript
from app.ai.stt import FakeSTT, Segment, UnconfiguredSTT
from app.repositories import meetings as meetings_repo
from app.services.transcription import run_transcription

pytestmark = pytest.mark.db

CTX = {"title": "Họp ghi âm", "meeting_date": "2026-10-08", "project": "pay"}
SEGMENTS = [
    Segment(speaker="spk_1", start=5.0, end=19.0, text="Hôm nay mình chốt CSDL nhé."),
    Segment(speaker="spk_2", start=20.0, end=30.0, text="Em đề xuất dùng MongoDB."),
    Segment(speaker="spk_1", start=210.0, end=215.0, text="Vậy mình chốt Postgres nhé."),
]
MAPPING = [
    {"label": "Người nói A", "name": "Lan", "is_decision_maker": True},
    {"label": "Người nói B", "name": "Minh", "is_decision_maker": False},
]


async def upload_audio(client: httpx.AsyncClient, data: bytes = b"ID3fake-audio") -> httpx.Response:
    return await client.post(
        "/meetings",
        files={"file": ("hop.m4a", data)},
        data={"context": json.dumps(CTX)},
        headers=auth(),
    )


async def transcribed(
    client: httpx.AsyncClient,
    sm: async_sessionmaker[AsyncSession],
    segments: list[Segment] = SEGMENTS,
) -> tuple[str, str]:
    r = await upload_audio(client)
    assert r.status_code == 201
    mid, jid = r.json()["meeting_id"], r.json()["job_id"]
    await run_transcription(sm, FakeSTT(segments), org_id="org_a", meeting_id=mid, job_id=jid)
    return mid, jid


async def test_audio_upload_enqueues_transcription(
    client: httpx.AsyncClient, queue: FakeQueue
) -> None:
    r = await upload_audio(client)
    assert r.status_code == 201
    mid, jid = r.json()["meeting_id"], r.json()["job_id"]
    assert queue.calls == [("transcribe", "org_a", mid, jid)]
    m = (await client.get(f"/meetings/{mid}", headers=auth())).json()
    assert m["status"] == "transcribing"
    assert m["active_job_id"] == jid


async def test_audio_size_limit_is_separate_from_transcript_limit(
    client: httpx.AsyncClient, app: object
) -> None:
    app.state.settings.max_audio_bytes = 100  # type: ignore[attr-defined]
    r = await upload_audio(client, b"a" * 101)
    assert r.status_code == 413
    assert (await upload_audio(client, b"a" * 100)).status_code == 201


async def test_transcription_stores_labelled_txt_and_waits_for_speakers(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid, _ = await transcribed(client, sessionmaker)
    m = (await client.get(f"/meetings/{mid}", headers=auth())).json()
    assert m["status"] == "awaiting_speakers"
    assert m["latest_job"]["status"] == "succeeded"
    async with sessionmaker() as s:
        row = await meetings_repo.get(s, org_id="org_a", meeting_id=mid, with_source=True)
        assert row is not None
        assert row.source_filename == "hop.txt"
        utts = parse_transcript(row.source_filename, row.source_bytes)
    assert [u.speaker for u in utts] == ["Người nói A", "Người nói B", "Người nói A"]

    r = await client.get(f"/meetings/{mid}/speakers", headers=auth())
    assert r.status_code == 200
    assert r.json() == [
        {"label": "Người nói A", "count": 2,
         "samples": ["Hôm nay mình chốt CSDL nhé.", "Vậy mình chốt Postgres nhé."]},
        {"label": "Người nói B", "count": 1, "samples": ["Em đề xuất dùng MongoDB."]},
    ]


async def test_assign_speakers_renames_and_starts_analysis(
    client: httpx.AsyncClient, queue: FakeQueue, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    mid, _ = await transcribed(client, sessionmaker)
    r = await client.post(f"/meetings/{mid}/speakers", json={"speakers": MAPPING}, headers=auth())
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    assert queue.calls[-1] == ("analyze", "org_a", mid, job_id)

    m = (await client.get(f"/meetings/{mid}", headers=auth())).json()
    assert m["status"] == "analyzing"
    assert m["active_job_id"] == job_id
    assert m["context"]["participants"] == [
        {"name": "Lan", "role": None, "is_decision_maker": True},
        {"name": "Minh", "role": None, "is_decision_maker": False},
    ]
    async with sessionmaker() as s:
        row = await meetings_repo.get(s, org_id="org_a", meeting_id=mid, with_source=True)
        assert row is not None
        utts = parse_transcript(row.source_filename, row.source_bytes)
    assert [u.speaker for u in utts] == ["Lan", "Minh", "Lan"]

    again = await client.post(f"/meetings/{mid}/speakers", json={"speakers": MAPPING}, headers=auth())
    assert again.status_code == 409
    assert (await client.get(f"/meetings/{mid}/speakers", headers=auth())).status_code == 409


@pytest.mark.parametrize(
    "speakers",
    [
        [MAPPING[0]],  # missing a label
        [*MAPPING, {"label": "Người nói C", "name": "Hoa"}],  # unknown label
        [MAPPING[0], {**MAPPING[1], "name": "lan"}],  # duplicate name
        [MAPPING[0], {**MAPPING[1], "name": "Minh: x"}],  # colon breaks the line format
        [MAPPING[0], {**MAPPING[1], "name": "   "}],  # blank
        [MAPPING[0], {**MAPPING[1], "name": "9Minh"}],  # must start with a letter
    ],
)
async def test_invalid_speaker_assignment_is_422(
    client: httpx.AsyncClient,
    sessionmaker: async_sessionmaker[AsyncSession],
    speakers: list[dict[str, object]],
) -> None:
    mid, _ = await transcribed(client, sessionmaker)
    r = await client.post(f"/meetings/{mid}/speakers", json={"speakers": speakers}, headers=auth())
    assert r.status_code == 422
    m = (await client.get(f"/meetings/{mid}", headers=auth())).json()
    assert m["status"] == "awaiting_speakers"


async def test_speakers_on_transcript_meeting_is_409(
    client: httpx.AsyncClient, transcript_bytes: bytes
) -> None:
    r = await client.post(
        "/meetings",
        files={"file": ("t.txt", transcript_bytes)},
        data={"context": json.dumps(CTX)},
        headers=auth(),
    )
    mid = r.json()["meeting_id"]
    assert (await client.get(f"/meetings/{mid}/speakers", headers=auth())).status_code == 409


async def test_failed_transcription_can_be_retried(
    client: httpx.AsyncClient, queue: FakeQueue, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    r = await upload_audio(client)
    mid, jid = r.json()["meeting_id"], r.json()["job_id"]
    await run_transcription(sessionmaker, UnconfiguredSTT(), org_id="org_a", meeting_id=mid, job_id=jid)
    m = (await client.get(f"/meetings/{mid}", headers=auth())).json()
    assert m["status"] == "failed"
    assert "OPENAI_API_KEY" in m["latest_job"]["error"]

    retry = await client.post(f"/meetings/{mid}/reanalyze", headers=auth())
    assert retry.status_code == 202
    assert queue.calls[-1] == ("transcribe", "org_a", mid, retry.json()["job_id"])
    m = (await client.get(f"/meetings/{mid}", headers=auth())).json()
    assert m["status"] == "transcribing"


async def test_empty_transcription_fails_with_message(
    client: httpx.AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    r = await upload_audio(client)
    mid, jid = r.json()["meeting_id"], r.json()["job_id"]
    silent = [Segment(speaker="x", start=0.0, end=1.0, text="  ")]
    await run_transcription(sessionmaker, FakeSTT(silent), org_id="org_a", meeting_id=mid, job_id=jid)
    m = (await client.get(f"/meetings/{mid}", headers=auth())).json()
    assert m["status"] == "failed"
    assert "lời thoại" in m["latest_job"]["error"]
