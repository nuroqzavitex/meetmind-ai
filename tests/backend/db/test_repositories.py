from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.domain.enums import Act, ItemType
from app.ai.domain.models import DialogueAct, Evidence, MeetingContext, MeetingItem, Utterance
from app.ai.domain.state_machine import Topic
from app.core.auth import Principal
from app.models import DialogueActRow, Item, Job, TopicRow
from app.models import Utterance as UtteranceRow
from app.repositories import items, jobs, meetings

pytestmark = pytest.mark.db

SM = async_sessionmaker[AsyncSession]


def _ctx(mid: str, d: date, project: str | None) -> MeetingContext:
    return MeetingContext(meeting_id=mid, title=f"T {mid}", meeting_date=d, project=project)


def _utts() -> list[Utterance]:
    return [
        Utterance(id=f"u{i:04d}", seq=i, speaker="An", start=float(i), text=f"text {i}")
        for i in range(3)
    ]


def _act() -> DialogueAct:
    return DialogueAct(
        id="a1", utterance_id="u0000", seq=0, speaker="An", start=0.0, act=Act.DECIDE, quote="x"
    )


def _item(mid: str) -> MeetingItem:
    return MeetingItem(
        id=f"{mid}-i001",
        meeting_id=mid,
        type=ItemType.ACTION_ITEM,
        content="Do it",
        due_date=date(2026, 10, 16),
        evidence=[Evidence(utterance_id="u0000", speaker="An", ts="00:00:01", quote="x")],
    )


async def _mk(s: AsyncSession, org: str, mid: str, d: date, project: str | None) -> None:
    await meetings.create(
        s, org_id=org, created_by="u1", ctx=_ctx(mid, d, project), filename="f.vtt", data=b"x"
    )


async def test_meeting_roundtrip_and_list_filters(sessionmaker: SM) -> None:
    async with sessionmaker() as s:
        await _mk(s, "org_a", "m1", date(2026, 10, 1), "pay")
        await _mk(s, "org_a", "m2", date(2026, 10, 5), "crm")
        await _mk(s, "org_b", "m3", date(2026, 10, 9), "pay")
        await s.commit()
        got = await meetings.get(s, org_id="org_a", meeting_id="m1")
        assert got is not None and got.status == "draft" and got.project == "pay"
        assert [m.id for m in await meetings.list_(s, org_id="org_a")] == ["m2", "m1"]
        pay = await meetings.list_(s, org_id="org_a", project="pay")
        assert [m.id for m in pay] == ["m1"]
        assert len(await meetings.list_(s, org_id="org_a", status="draft")) == 2
        assert await meetings.list_(s, org_id="org_a", status="published") == []


async def test_cross_org_get_returns_none(sessionmaker: SM) -> None:
    async with sessionmaker() as s:
        await _mk(s, "org_a", "m1", date(2026, 10, 1), None)
        job = await jobs.create(s, org_id="org_a", meeting_id="m1", kind="analyze")
        await meetings.replace_analysis(
            s,
            org_id="org_a",
            meeting_id="m1",
            utterances=_utts(),
            acts=[_act()],
            topics=[Topic(topic_id="t1", question="q")],
        )
        created = await items.replace_for_meeting(
            s, org_id="org_a", meeting_id="m1", items=[_item("m1")]
        )
        await s.commit()
        assert await meetings.get(s, org_id="org_b", meeting_id="m1") is None
        assert await jobs.get(s, org_id="org_b", job_id=job.id) is None
        assert await items.get(s, org_id="org_b", item_id=created[0].id) is None
        assert await meetings.get_utterances(s, org_id="org_b", meeting_id="m1") == []
        assert await meetings.get_topics(s, org_id="org_b", meeting_id="m1") == []
        assert await items.list_for_meeting(s, org_id="org_b", meeting_id="m1") == []
        assert len(await meetings.get_utterances(s, org_id="org_a", meeting_id="m1")) == 3
        assert await jobs.get(s, org_id="org_a", job_id=job.id) is not None


async def test_replace_analysis_is_idempotent(sessionmaker: SM) -> None:
    async with sessionmaker() as s:
        await _mk(s, "org_a", "m1", date(2026, 10, 1), None)
        topic = Topic(topic_id="t1", question="q", ambiguous_decides=[_act()])
        for _ in range(2):
            await meetings.replace_analysis(
                s,
                org_id="org_a",
                meeting_id="m1",
                utterances=_utts(),
                acts=[_act()],
                topics=[topic],
            )
            await items.replace_for_meeting(s, org_id="org_a", meeting_id="m1", items=[_item("m1")])
        await s.commit()
        for model in (UtteranceRow, DialogueActRow, TopicRow):
            assert await s.scalar(select(func.count()).select_from(model)) == (
                3 if model is UtteranceRow else 1
            )
        assert len(await items.list_for_meeting(s, org_id="org_a", meeting_id="m1")) == 1
        utts = await meetings.get_utterances(s, org_id="org_a", meeting_id="m1")
        assert [u.seq for u in utts] == [0, 1, 2] and utts == _utts()
        assert await meetings.get_topics(s, org_id="org_a", meeting_id="m1") == [topic]


async def test_item_model_roundtrip(sessionmaker: SM) -> None:
    async with sessionmaker() as s:
        await _mk(s, "org_a", "m1", date(2026, 10, 1), None)
        original = _item("m1")
        rows = await items.replace_for_meeting(s, org_id="org_a", meeting_id="m1", items=[original])
        await s.commit()
        assert items.to_model(rows[0]) == original
        got = await items.get(s, org_id="org_a", item_id=original.id)
        assert got is not None and items.to_model(got) == original
        edited = original.model_copy(update={"content": "Changed"})
        await items.save(s, item=got, model=edited)
        ev = await items.add_event(
            s, item=got, actor=Principal(user_id="u1", org_id="org_a", name="An"), action="edited"
        )
        await s.commit()
        assert items.to_model(got).content == "Changed"
        evs = await items.events(s, org_id="org_a", item_id=original.id)
        assert [e.pk for e in evs] == [ev.pk] and evs[0].actor_name == "An"
        assert await items.events(s, org_id="org_b", item_id=original.id) == []


async def test_active_job(sessionmaker: SM) -> None:
    async with sessionmaker() as s:
        await _mk(s, "org_a", "m1", date(2026, 10, 1), None)
        job = await jobs.create(s, org_id="org_a", meeting_id="m1", kind="analyze")
        await s.commit()
        active = await jobs.active_for_meeting(s, org_id="org_a", meeting_id="m1")
        assert active is not None and active.id == job.id and active.status == "queued"
        await jobs.update(s, org_id="org_a", job_id=job.id, status="succeeded")
        await s.commit()
        assert await jobs.active_for_meeting(s, org_id="org_a", meeting_id="m1") is None
        with pytest.raises(AttributeError):
            await jobs.update(s, org_id="org_a", job_id=job.id, bogus=1)


async def test_set_status_and_published_at(sessionmaker: SM) -> None:
    from datetime import UTC, datetime

    ts = datetime(2026, 10, 10, tzinfo=UTC)
    async with sessionmaker() as s:
        await _mk(s, "org_a", "m1", date(2026, 10, 1), None)
        await meetings.set_status(
            s, org_id="org_a", meeting_id="m1", status="published", published_at=ts
        )
        await s.commit()
        s.expire_all()
        m = await meetings.get(s, org_id="org_a", meeting_id="m1")
        assert m is not None and m.status == "published" and m.published_at == ts


async def test_cross_org_mutators_are_noops(sessionmaker: SM) -> None:
    async with sessionmaker() as s:
        await _mk(s, "org_b", "mb", date(2026, 10, 1), None)
        await meetings.replace_analysis(
            s, org_id="org_b", meeting_id="mb", utterances=_utts(), acts=[], topics=[]
        )
        await items.replace_for_meeting(s, org_id="org_b", meeting_id="mb", items=[_item("mb")])
        job_id = (await jobs.create(s, org_id="org_b", meeting_id="mb", kind="analyze")).id
        await s.commit()

        await meetings.replace_analysis(
            s, org_id="org_a", meeting_id="mb", utterances=[], acts=[], topics=[]
        )
        assert (
            await items.replace_for_meeting(
                s,
                org_id="org_a",
                meeting_id="mb",
                items=[_item("mb").model_copy(update={"id": "x"})],
            )
            == []
        )
        await meetings.set_status(s, org_id="org_a", meeting_id="mb", status="failed")
        await jobs.update(s, org_id="org_a", job_id=job_id, status="failed")
        with pytest.raises(LookupError):
            await jobs.create(s, org_id="org_a", meeting_id="mb", kind="analyze")
        with pytest.raises(AttributeError):
            await jobs.update(s, org_id="org_b", job_id=job_id, meeting_id="other")
        await s.commit()
        s.expire_all()

        assert len(await meetings.get_utterances(s, org_id="org_b", meeting_id="mb")) == 3
        its = await items.list_for_meeting(s, org_id="org_b", meeting_id="mb")
        assert [i.id for i in its] == ["mb-i001"]
        m = await meetings.get(s, org_id="org_b", meeting_id="mb")
        assert m is not None and m.status == "draft"
        j = await jobs.get(s, org_id="org_b", job_id=job_id)
        assert j is not None and j.status == "queued"
        assert await s.scalar(select(func.count()).select_from(Item)) == 1
        assert await s.scalar(select(func.count()).select_from(Job)) == 1


async def test_source_bytes_deferred_unless_requested(sessionmaker: SM) -> None:
    async with sessionmaker() as s:
        await meetings.create(
            s, org_id="org_a", created_by="u", ctx=_ctx("md", date(2026, 1, 1), None),
            filename="a.txt", data=b"payload",
        )
        await s.commit()
    async with sessionmaker() as s:
        listed = await meetings.list_(s, org_id="org_a")
        assert "source_bytes" in sa_inspect(listed[0]).unloaded
    async with sessionmaker() as s:
        row = await meetings.get(s, org_id="org_a", meeting_id="md", with_source=True)
        assert row is not None and row.source_bytes == b"payload"
