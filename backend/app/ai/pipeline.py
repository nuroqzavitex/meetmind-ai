"""LangGraph analysis pipeline: transcript bytes -> MeetingItems (spec 8.1)."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.ai.agents.arbitrate import apply_arbitration, arbitrate, arbitration_reasons
from app.ai.agents.build_items import build_items
from app.ai.agents.check_quotes import check_quotes
from app.ai.agents.extract import dedupe_acts, extract_chunk
from app.ai.agents.normalize import Chunk, apply_glossary, make_chunks
from app.ai.agents.topics import TopicSpec, assign_topics
from app.ai.agents.validate import validate_items
from app.ai.config import AISettings
from app.ai.domain.commitment_guard import guard_items
from app.ai.domain.decide_guard import guard_acts
from app.ai.domain.models import DialogueAct, MeetingContext, MeetingItem, Utterance
from app.ai.domain.state_machine import Topic, run_topic
from app.ai.errors import AnalysisError, TranscriptParseError
from app.ai.llm import LLMClient
from app.ai.parsing import parse_transcript

ProgressFn = Callable[[str, float], Awaitable[None]]
BAD_RATIO_RETRY = 0.3
PROGRESS = {
    "normalize": 0.05, "extract": 0.15, "check_quotes": 0.5, "topics": 0.6,
    "state_machine": 0.7, "arbitrate": 0.8, "build_items": 0.9, "validate": 0.95,
}


class AnalysisResult(BaseModel):
    utterances: list[Utterance]
    acts: list[DialogueAct]
    topics: list[Topic]
    specs: list[TopicSpec]
    items: list[MeetingItem]


class State(TypedDict, total=False):
    utterances: list[Utterance]
    chunks: list[Chunk]
    todo: list[int]  # chunk indexes the next extract run must (re)process
    acts_by_chunk: dict[int, list[DialogueAct]]
    retried: set[int]
    acts: list[DialogueAct]
    topics: list[Topic]
    specs: list[TopicSpec]
    items: list[MeetingItem]


class NodeFn(Protocol):
    def __call__(self, state: State) -> Coroutine[Any, Any, dict[str, Any]]: ...


async def analyze_transcript(
    *,
    ctx: MeetingContext,
    filename: str,
    data: bytes,
    llm: LLMClient,
    settings: AISettings,
    on_progress: ProgressFn | None = None,
) -> AnalysisResult:
    sem = asyncio.Semaphore(settings.max_concurrency)
    last = 0.0

    async def report(step: str, value: float) -> None:
        nonlocal last
        last = max(last, value)
        if on_progress is not None:
            await on_progress(step, last)

    def node(name: str, fn: NodeFn) -> NodeFn:
        async def run(state: State) -> dict[str, Any]:
            await report(name, PROGRESS[name])
            try:
                return await fn(state)
            except (TranscriptParseError, AnalysisError):
                raise
            except Exception as e:  # LLMError and unexpected bugs alike
                raise AnalysisError(f"{name} failed: {e}", step=name) from e

        return run

    async def n_normalize(state: State) -> dict[str, Any]:
        utts = apply_glossary(parse_transcript(filename, data), ctx.glossary)
        chunks = make_chunks(utts)
        return {"utterances": utts, "chunks": chunks, "todo": [c.index for c in chunks]}

    async def n_extract(state: State) -> dict[str, Any]:
        async def one(chunk: Chunk) -> tuple[int, list[DialogueAct]]:
            async with sem:
                acts = await extract_chunk(llm, ctx, chunk, settings.prompt_version)
            return chunk.index, acts

        chunks = [state["chunks"][i] for i in state["todo"]]
        got = await asyncio.gather(*(one(c) for c in chunks))
        return {"acts_by_chunk": {**state.get("acts_by_chunk", {}), **dict(got)}}

    async def n_check_quotes(state: State) -> dict[str, Any]:
        by_id = {u.id: u for u in state["utterances"]}
        retried = set(state.get("retried", set()))
        valid_by_chunk = dict(state["acts_by_chunk"])
        todo: list[int] = []
        for idx in state["todo"]:
            valid, bad = check_quotes(state["acts_by_chunk"][idx], by_id)
            valid_by_chunk[idx] = valid
            if bad > BAD_RATIO_RETRY and idx not in retried:
                retried.add(idx)
                todo.append(idx)
        return {"acts_by_chunk": valid_by_chunk, "retried": retried, "todo": todo}

    async def n_topics(state: State) -> dict[str, Any]:
        merged = [a for i in sorted(state["acts_by_chunk"]) for a in state["acts_by_chunk"][i]]
        specs, acts = await assign_topics(llm, ctx, dedupe_acts(merged), settings.prompt_version)
        return {"specs": specs, "acts": guard_acts(acts)}

    async def n_state_machine(state: State) -> dict[str, Any]:
        topics = [
            run_topic(
                Topic(topic_id=s.topic_id, question=s.question),
                [a for a in state["acts"] if a.topic_id == s.topic_id],
            )
            for s in state["specs"]
        ]
        return {"topics": topics}

    async def n_arbitrate(state: State) -> dict[str, Any]:
        topics: list[Topic] = []
        for t in state["topics"]:
            t_acts = [a for a in state["acts"] if a.topic_id == t.topic_id]
            reasons = arbitration_reasons(t, ctx, t_acts)
            if reasons:
                result = await arbitrate(
                    llm, t, state["utterances"], reasons, settings.prompt_version
                )
                t = apply_arbitration(t, result)
            topics.append(t)
        return {"topics": topics}

    async def n_build_items(state: State) -> dict[str, Any]:
        items = build_items(ctx, state["topics"], state["specs"], state["acts"])
        return {"items": guard_items(items, state["utterances"])}

    async def n_validate(state: State) -> dict[str, Any]:
        return {"items": validate_items(state["items"])}

    def after_check(state: State) -> str:
        return "extract" if state["todo"] else "topics"

    graph = StateGraph(State)
    steps = {
        "normalize": n_normalize, "extract": n_extract, "check_quotes": n_check_quotes,
        "topics": n_topics, "state_machine": n_state_machine, "arbitrate": n_arbitrate,
        "build_items": n_build_items, "validate": n_validate,
    }
    for name, fn in steps.items():
        graph.add_node(name, node(name, fn))
    graph.add_edge(START, "normalize")
    graph.add_edge("normalize", "extract")
    graph.add_edge("extract", "check_quotes")
    graph.add_conditional_edges("check_quotes", after_check, ["extract", "topics"])
    for a, b in [("topics", "state_machine"), ("state_machine", "arbitrate"),
                 ("arbitrate", "build_items"), ("build_items", "validate"), ("validate", END)]:
        graph.add_edge(a, b)

    final = await graph.compile().ainvoke({"retried": set(), "acts_by_chunk": {}})
    await report("done", 1.0)
    return AnalysisResult(
        utterances=final["utterances"], acts=final["acts"], topics=final["topics"],
        specs=final["specs"], items=final["items"],
    )
