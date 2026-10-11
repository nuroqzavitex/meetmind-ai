"""Knowledge Q&A over published meetings: retrieve, expand supersession, answer, cite."""

import logging
import re
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.qa import (
    REFUSAL,
    QAContext,
    answer_question,
    check_citations,
    extract_filter,
)
from app.ai.config import AISettings
from app.ai.domain.timefmt import fmt_ts
from app.ai.errors import EmbeddingError, LLMError, LLMRefusal
from app.ai.llm import LLMClient
from app.ai.retrieval.embedder import Embedder
from app.core.auth import Principal
from app.core.errors import ServiceUnavailable
from app.models import Item, Meeting, TranscriptChunk
from app.repositories import search
from app.repositories.items import to_model
from app.schemas.qa import Citation, QAResponse

log = logging.getLogger(__name__)

MAX_CONTEXTS = 12
MAX_TOTAL = 16
_MARKER = re.compile(r"\[(\d+)\]")


def _refusal() -> QAResponse:
    return QAResponse(answer=REFUSAL, citations=[])


def _item_context(item: Item, meeting: Meeting) -> QAContext:
    model = to_model(item)
    ev = model.evidence[0] if model.evidence else None
    return QAContext(
        ref=0,
        kind="item",
        meeting_id=item.meeting_id,
        meeting_title=meeting.title,
        meeting_date=meeting.meeting_date,
        text=item.search_text or model.content,
        utterance_id=ev.utterance_id if ev else "",
        ts=ev.ts if ev else "",
        speaker=ev.speaker if ev else "",
        quote=ev.quote if ev else "",
    )


def _chunk_context(chunk: TranscriptChunk, meeting: Meeting) -> QAContext:
    first_line = chunk.text.split("\n", 1)[0]
    return QAContext(
        ref=0,
        kind="chunk",
        meeting_id=chunk.meeting_id,
        meeting_title=meeting.title,
        meeting_date=meeting.meeting_date,
        text=chunk.text,
        utterance_id=chunk.first_utterance_id,
        ts=fmt_ts(chunk.start_ts),
        speaker=chunk.speakers[0] if chunk.speakers else "",
        quote=first_line.partition(": ")[2] or first_line,
    )


async def ask(
    session: AsyncSession,
    llm: LLMClient,
    embedder: Embedder,
    ai: AISettings,
    *,
    principal: Principal,
    question: str,
    project: str | None,
    today: date,
) -> QAResponse:
    try:
        return await _ask(
            session, llm, embedder, ai,
            principal=principal, question=question, project=project, today=today,
        )
    except LLMRefusal:
        return _refusal()
    except LLMError as e:
        log.warning("QA LLM call failed: %s", e)
        raise ServiceUnavailable(
            "Dịch vụ AI chưa sẵn sàng, vui lòng thử lại sau", "llm_unavailable"
        ) from e
    except EmbeddingError as e:
        log.warning("QA embedding failed: %s", e)
        raise ServiceUnavailable(
            "Dịch vụ tìm kiếm chưa sẵn sàng", "embedding_unavailable"
        ) from e


async def _ask(
    session: AsyncSession,
    llm: LLMClient,
    embedder: Embedder,
    ai: AISettings,
    *,
    principal: Principal,
    question: str,
    project: str | None,
    today: date,
) -> QAResponse:
    org_id = principal.org_id
    projects = await search.org_projects(session, org_id=org_id)
    if not await search.has_published(session, org_id=org_id):
        return _refusal()

    f = await extract_filter(
        llm, question=question, projects=projects, today=today, prompt_version=ai.prompt_version
    )
    if project:
        canon = {p.casefold(): p for p in projects}
        chosen = canon.get(project.strip().casefold())
        if chosen is not None:
            f.project = chosen
    filters = search.SearchFilters(
        project=f.project,
        date_from=f.date_from,
        date_to=f.date_to,
        people=list(f.people),
        item_types=[t.value for t in f.item_types],
    )
    vec = (await embedder.embed([f.rewritten_query]))[0]
    hits = (
        await search.hybrid_search(
            session, org_id=org_id, query=f.rewritten_query, query_vec=vec, filters=filters
        )
    )[:MAX_CONTEXTS]
    if not hits and (filters.people or filters.date_from or filters.date_to or filters.item_types):
        # LLM-derived filters may be too narrow: retry once with the project filter only.
        hits = (
            await search.hybrid_search(
                session,
                org_id=org_id,
                query=f.rewritten_query,
                query_vec=vec,
                filters=search.SearchFilters(project=f.project),
            )
        )[:MAX_CONTEXTS]
    if not hits:
        return _refusal()

    meetings = await search.meetings_by_id(
        session, org_id=org_id, ids=sorted({h.meeting_id for h in hits})
    )
    items = await search.load_items(
        session, org_id=org_id, ids=[h.id for h in hits if h.kind == "item"]
    )
    chunks = await search.load_chunks(
        session, org_id=org_id, ids=[h.id for h in hits if h.kind == "chunk"]
    )
    built: list[tuple[QAContext, str | None]] = []  # (context, item id)
    for h in hits:
        meeting = meetings.get(h.meeting_id)
        if meeting is None:
            continue
        if h.kind == "item" and h.id in items:
            built.append((_item_context(items[h.id], meeting), h.id))
        elif h.kind == "chunk" and h.id in chunks:
            built.append((_chunk_context(chunks[h.id], meeting), None))
    if not built:
        return _refusal()

    # Supersession expansion: surface the final decision for options mentioned in the hits.
    decisions = await search.decisions_for_meetings(
        session, org_id=org_id, meeting_ids=sorted({c.meeting_id for c, _ in built})
    )
    present = {iid: ctx for ctx, iid in built if iid}
    to_add: list[tuple[QAContext, str]] = []
    for d in decisions:
        patterns = [
            re.compile(rf"(?<!\w){re.escape(label)}(?!\w)", re.UNICODE)
            for label in (x.strip().casefold() for x in to_model(d).supersedes)
            if len(label) >= 3
        ]
        if not patterns:
            continue
        triggered = False
        for ctx, iid in built:
            if iid == d.id or ctx.meeting_id != d.meeting_id:
                continue
            text = ctx.text.casefold()
            if any(p.search(text) for p in patterns):
                ctx.marker = "đã bị thay thế"
                triggered = True
        if not triggered:
            continue
        if d.id in present:
            present[d.id].marker = "mới nhất"
        elif len(built) + len(to_add) < MAX_TOTAL and meetings.get(d.meeting_id):
            ctx = _item_context(d, meetings[d.meeting_id])
            ctx.marker = "mới nhất"
            to_add.append((ctx, d.id))
    built.extend(to_add)

    contexts = sorted(
        (c for c, _ in built),
        key=lambda c: (c.meeting_date, meetings[c.meeting_id].created_at, c.meeting_id, c.ts),
    )
    for i, c in enumerate(contexts, 1):
        c.ref = i

    answer = await answer_question(
        llm, question=question, contexts=contexts, prompt_version=ai.prompt_version
    )
    text, cited = check_citations(answer, contexts)
    if not cited:
        return _refusal()

    new_ref = {c.ref: n for n, c in enumerate(cited, 1)}
    text = _MARKER.sub(lambda m: f"[{new_ref.get(int(m.group(1)), int(m.group(1)))}]", text)
    return QAResponse(
        answer=text,
        citations=[
            Citation(
                ref=new_ref[c.ref],
                meeting_id=c.meeting_id,
                title=c.meeting_title,
                date=c.meeting_date,
                ts=c.ts,
                speaker=c.speaker,
                quote=c.quote,
                utterance_id=c.utterance_id,
            )
            for c in cited
        ],
    )
