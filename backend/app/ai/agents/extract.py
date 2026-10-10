"""Agent 2: extract dialogue acts from a chunk of utterances."""

from pydantic import BaseModel, Field

from app.ai.agents.normalize import Chunk
from app.ai.domain.enums import Act
from app.ai.domain.models import DialogueAct, MeetingContext
from app.ai.domain.timefmt import fmt_ts
from app.ai.llm import LLMClient, load_prompt


class RawAct(BaseModel):
    """Schema returned by the LLM (no id/seq/speaker/start/topic_id/due_date)."""

    utterance_id: str
    act: Act
    quote: str
    topic_hint: str | None = None
    option: str | None = None
    content: str | None = None
    assignee: str | None = None
    due_text: str | None = None
    condition: str | None = None
    confidence: float = Field(ge=0, le=1)


class ExtractOutput(BaseModel):
    acts: list[RawAct]


def render_chunk(chunk: Chunk) -> str:
    return "\n".join(
        f"{u.id} [{fmt_ts(u.start)}] {u.speaker}: {u.text}" for u in chunk.utterances
    )


def render_context(ctx: MeetingContext) -> str:
    lines = ["## Ngữ cảnh cuộc họp", f"Tiêu đề: {ctx.title}", f"Ngày: {ctx.meeting_date.isoformat()}"]
    if ctx.participants:
        lines.append("Người tham gia:")
        for p in ctx.participants:
            extra = ", ".join(
                x for x in (p.role, "người ra quyết định" if p.is_decision_maker else None) if x
            )
            lines.append(f"- {p.name}" + (f" ({extra})" if extra else ""))
    if ctx.glossary:
        lines.append("Thuật ngữ: " + ", ".join(ctx.glossary))
    return "\n".join(lines)


async def extract_chunk(
    llm: LLMClient, ctx: MeetingContext, chunk: Chunk, prompt_version: str
) -> list[DialogueAct]:
    system = load_prompt("extract", prompt_version) + "\n\n" + render_context(ctx)
    out = await llm.structured(
        agent="extract", system=system, user=render_chunk(chunk), schema=ExtractOutput
    )
    by_id = {u.id: u for u in chunk.utterances}
    counters: dict[str, int] = {}
    acts: list[DialogueAct] = []
    for raw in out.acts:
        u = by_id.get(raw.utterance_id)
        if u is None:
            continue
        n = counters.get(u.id, 0)
        counters[u.id] = n + 1
        acts.append(
            DialogueAct(
                id=f"a{u.seq:04d}_{n}",
                seq=u.seq,
                speaker=u.speaker,
                start=u.start,
                **raw.model_dump(),
            )
        )
    return acts


def dedupe_acts(acts: list[DialogueAct]) -> list[DialogueAct]:
    best: dict[tuple[str, Act, str | None], DialogueAct] = {}
    for a in acts:
        key = (a.utterance_id, a.act, a.option)
        cur = best.get(key)
        if cur is None or a.confidence > cur.confidence:
            best[key] = a
    ordered = sorted(best.values(), key=lambda a: (a.start, a.seq))
    counters: dict[str, int] = {}
    result: list[DialogueAct] = []
    for a in ordered:
        n = counters.get(a.utterance_id, 0)
        counters[a.utterance_id] = n + 1
        result.append(a.model_copy(update={"id": f"a{a.seq:04d}_{n}"}))
    return result
