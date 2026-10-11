import re
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, func, literal, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.backend.api_helpers import auth
from tests.backend.pipeline_helpers import seed_published_indexed_meeting

from app.ai.agents.qa import REFUSAL
from app.ai.errors import EmbeddingError, LLMError, LLMRefusal
from app.ai.llm.fake import FakeLLM
from app.ai.retrieval.embedder import HashEmbedder
from app.models import Item, Meeting, TranscriptChunk

pytestmark = pytest.mark.db

SM = async_sessionmaker[AsyncSession]
Q = "Dịch vụ thanh toán dùng CSDL nào?"


def _filter(query: str = Q, **kw: Any) -> dict[str, Any]:
    return {"rewritten_query": query, **kw}


def _block_ref(user: str, *needles: str) -> int:
    ctx = user.split("<ngu_canh>")[1].split("</ngu_canh>")[0]
    for block in ctx.strip().split("\n\n"):
        if all(n in block for n in needles):
            return int(re.match(r"\[(\d+)\]", block).group(1))  # type: ignore[union-attr]
    raise AssertionError(f"no block with {needles}\n{ctx}")


def _postgres_answer(user: str) -> dict[str, Any]:
    n = _block_ref(user, "Quyết định:", "Postgres")
    return {"answer": f"Dùng Postgres [{n}]", "used_refs": [n]}


async def _seed(sessionmaker: SM, **kw: Any) -> str:
    return await seed_published_indexed_meeting(sessionmaker, HashEmbedder(1024), **kw)


async def test_answer_with_citation(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker)
    llm = FakeLLM({"qa_filter": [_filter()], "qa": [_postgres_answer]})
    app.state.llm = llm
    r = await client.post("/qa", json={"question": Q}, headers=auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"] == "Dùng Postgres [1]"
    assert len(body["citations"]) == 1
    c = body["citations"][0]
    assert c["ref"] == 1 and c["meeting_id"] == "m1"
    assert c["ts"] == "00:03:30" and c["speaker"] == "Lan"
    assert c["utterance_id"] and c["quote"] and c["date"] == "2026-10-08"
    assert c["title"] == "Payment sprint planning"


async def test_citations_renumbered_in_citation_order(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker)

    def answer(user: str) -> dict[str, Any]:
        item = _block_ref(user, "Quyết định:", "Postgres")
        chunk = _block_ref(user, "Lan: Vậy mình chốt Postgres")
        assert item != chunk
        return {"answer": f"A [{chunk}] B [{item}]", "used_refs": []}

    app.state.llm = FakeLLM({"qa_filter": [_filter()], "qa": [answer]})
    r = await client.post("/qa", json={"question": Q}, headers=auth())
    body = r.json()
    assert [c["ref"] for c in body["citations"]] == [1, 2]
    assert body["answer"] == "A [1] B [2]"


async def test_superseded_option_surfaces_final_decision(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker)
    llm = FakeLLM(
        {
            "qa_filter": [_filter("MongoDB", item_types=[])],
            "qa": [{"answer": REFUSAL, "used_refs": []}],
        }
    )
    app.state.llm = llm
    r = await client.post("/qa", json={"question": "Mình chọn MongoDB à?"}, headers=auth())
    assert r.status_code == 200
    user = dict(llm.calls)["qa"]
    ctx = user.split("<ngu_canh>")[1].split("</ngu_canh>")[0]
    latest = [b for b in ctx.strip().split("\n\n") if "mới nhất" in b.split("\n")[0]]
    assert latest and "Postgres" in latest[0]
    assert "đã bị thay thế" in ctx


async def test_refusal_without_published_meetings(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    llm = FakeLLM({})
    app.state.llm = llm
    r = await client.post("/qa", json={"question": Q}, headers=auth(org="org_fresh"))
    assert r.status_code == 200
    assert r.json() == {"answer": REFUSAL, "citations": []}
    assert llm.calls == []


async def test_refusal_when_llm_cites_nothing_valid(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker)
    app.state.llm = FakeLLM(
        {"qa_filter": [_filter()], "qa": [{"answer": "Dùng Postgres", "used_refs": [99]}]}
    )
    r = await client.post("/qa", json={"question": Q}, headers=auth())
    assert r.json() == {"answer": REFUSAL, "citations": []}


async def test_org_isolation_qa(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker, org_id="org_a", meeting_id="m1")
    await _seed(sessionmaker, org_id="org_b", meeting_id="m2")
    async with sessionmaker() as s:
        await s.execute(update(Meeting).where(Meeting.id == "m2").values(title="Chốt dùng MongoDB cho CRM"))
        await s.commit()
    llm = FakeLLM({"qa_filter": [_filter("MongoDB CRM")], "qa": [_postgres_answer]})
    app.state.llm = llm
    r = await client.post("/qa", json={"question": "MongoDB cho CRM?"}, headers=auth(org="org_a"))
    assert r.status_code == 200
    assert all(c["meeting_id"] != "m2" for c in r.json()["citations"])
    assert "CRM" not in dict(llm.calls)["qa"].split("<cau_hoi>")[0]


async def test_ui_project_overrides_filter(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker, meeting_id="m1", project="Alpha")
    await _seed(sessionmaker, meeting_id="m2", project="Beta")
    async with sessionmaker() as s:
        await s.execute(update(Meeting).where(Meeting.id == "m2").values(title="Beta-meeting-title"))
        await s.commit()
    llm = FakeLLM(
        {
            "qa_filter": [_filter(project="Beta")],
            "qa": [{"answer": REFUSAL, "used_refs": []}],
        }
    )
    app.state.llm = llm
    r = await client.post("/qa", json={"question": Q, "project": "Alpha"}, headers=auth())
    assert r.status_code == 200
    ctx = dict(llm.calls)["qa"]
    assert "Payment sprint planning" in ctx
    assert "Beta-meeting-title" not in ctx


async def test_requires_auth(client: httpx.AsyncClient) -> None:
    r = await client.post("/qa", json={"question": Q})
    assert r.status_code == 401


async def test_empty_question_422(client: httpx.AsyncClient) -> None:
    r = await client.post("/qa", json={"question": "   "}, headers=auth())
    assert r.status_code == 422


class _RaisingLLM:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls = 0

    async def structured(self, **_: Any) -> Any:
        self.calls += 1
        raise self.exc


class _RaisingEmbedder:
    dim = 1024

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("boom")


async def test_llm_error_is_503(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker)
    app.state.llm = _RaisingLLM(LLMError("down"))
    r = await client.post("/qa", json={"question": Q}, headers=auth())
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "llm_unavailable"
    assert "Dịch vụ AI" in r.json()["error"]["message"]


async def test_llm_refusal_is_refusal_response(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker)
    app.state.llm = _RaisingLLM(LLMRefusal("no"))
    r = await client.post("/qa", json={"question": Q}, headers=auth())
    assert r.status_code == 200
    assert r.json() == {"answer": REFUSAL, "citations": []}


async def test_embedding_error_is_503(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker)
    app.state.llm = FakeLLM({"qa_filter": [_filter()]})
    app.state.embedder = _RaisingEmbedder()
    r = await client.post("/qa", json={"question": Q}, headers=auth())
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "embedding_unavailable"


async def test_missing_api_key_is_503_but_empty_org_still_refuses(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker)
    app.state.llm = None
    app.state.settings = app.state.settings.model_copy(update={"anthropic_api_key": None})
    r = await client.post("/qa", json={"question": Q}, headers=auth())
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "llm_unavailable"
    r = await client.post("/qa", json={"question": Q}, headers=auth(org="org_fresh"))
    assert r.status_code == 200 and r.json()["answer"] == REFUSAL


async def test_refusal_when_only_other_org_has_published(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker, org_id="org_b", meeting_id="m2")
    llm = FakeLLM({})
    app.state.llm = llm
    r = await client.post("/qa", json={"question": Q}, headers=auth(org="org_a"))
    assert r.status_code == 200
    assert r.json() == {"answer": REFUSAL, "citations": []}
    assert llm.calls == []


async def test_narrow_llm_filters_fall_back_to_project_only(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker)
    llm = FakeLLM(
        {"qa_filter": [_filter(date_from="2030-01-01")], "qa": [_postgres_answer]}
    )
    app.state.llm = llm
    r = await client.post("/qa", json={"question": Q}, headers=auth())
    assert r.status_code == 200
    assert len(r.json()["citations"]) == 1


async def test_no_hits_even_after_fallback_refuses_after_filter_call_only(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker)
    async with sessionmaker() as s:
        await s.execute(update(Item).where(Item.meeting_id == "m1").values(embedding=None))
        await s.execute(delete(TranscriptChunk))
        await s.commit()
    llm = FakeLLM({"qa_filter": [_filter(date_from="2030-01-01")]})
    app.state.llm = llm
    r = await client.post("/qa", json={"question": Q}, headers=auth())
    assert r.status_code == 200
    assert r.json() == {"answer": REFUSAL, "citations": []}
    assert [a for a, _ in llm.calls] == ["qa_filter"]


_NON_DECISION = ["action_item", "blocker", "request", "feedback", "open_question", "knowledge"]


async def _only_non_decision_hits(sessionmaker: SM, text: str) -> None:
    async with sessionmaker() as s:
        await s.execute(delete(TranscriptChunk))
        await s.execute(
            update(Item)
            .where(Item.meeting_id == "m1", Item.type != "decision")
            .values(search_text=text)
        )
        await s.commit()


async def test_supersession_requires_whole_word_match(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker)
    await _only_non_decision_hits(sessionmaker, "Hành động: kiểm tra MongoDBX")
    llm = FakeLLM(
        {
            "qa_filter": [_filter("MongoDBX", item_types=_NON_DECISION)],
            "qa": [{"answer": REFUSAL, "used_refs": []}],
        }
    )
    app.state.llm = llm
    r = await client.post("/qa", json={"question": "MongoDBX?"}, headers=auth())
    assert r.status_code == 200
    ctx = dict(llm.calls)["qa"]
    assert "MongoDBX" in ctx
    assert "đã bị thay thế" not in ctx and "mới nhất" not in ctx


async def test_supersession_ignores_short_labels(
    app: FastAPI, client: httpx.AsyncClient, sessionmaker: SM
) -> None:
    await _seed(sessionmaker)
    async with sessionmaker() as s:
        await s.execute(
            update(Item)
            .where(Item.meeting_id == "m1", Item.type == "decision")
            .values(data=func.jsonb_set(Item.data, ["supersedes"], literal(["A"], JSONB)))
        )
        await s.commit()
    await _only_non_decision_hits(sessionmaker, "Hành động: phương án A cho việc kiểm tra")
    llm = FakeLLM(
        {
            "qa_filter": [_filter("phương án A", item_types=_NON_DECISION)],
            "qa": [{"answer": REFUSAL, "used_refs": []}],
        }
    )
    app.state.llm = llm
    r = await client.post("/qa", json={"question": "phương án A?"}, headers=auth())
    assert r.status_code == 200
    ctx = dict(llm.calls)["qa"]
    assert "phương án A" in ctx
    assert "đã bị thay thế" not in ctx and "mới nhất" not in ctx
