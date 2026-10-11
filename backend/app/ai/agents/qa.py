"""Q&A agent: filter extraction, grounded answer generation, citation post-check."""

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.ai.domain.enums import ItemType
from app.ai.llm import LLMClient, load_prompt

REFUSAL = "Không đủ thông tin trong các cuộc họp đã phát hành."
_MARKER = re.compile(r"\[(\d+)\]")


def _safe(text: str) -> str:
    """Neutralise `<` so untrusted text cannot open or close the prompt delimiter tags."""
    return text.replace("<", "‹")


class QAFilter(BaseModel):
    project: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    people: list[str] = []
    item_types: list[ItemType] = []
    rewritten_query: str


@dataclass
class QAContext:
    ref: int
    kind: Literal["item", "chunk"]
    meeting_id: str
    meeting_title: str
    meeting_date: date
    text: str
    utterance_id: str
    ts: str
    speaker: str
    quote: str
    marker: Literal["", "mới nhất", "đã bị thay thế"] = ""


class QAAnswer(BaseModel):
    answer: str
    used_refs: list[int]


async def extract_filter(
    llm: LLMClient, *, question: str, projects: list[str], today: date, prompt_version: str
) -> QAFilter:
    user = "\n".join(
        [
            "Dự án của tổ chức: " + (", ".join(projects) if projects else "(không có)"),
            f"Hôm nay: {today.isoformat()}",
            f"<cau_hoi>{_safe(question)}</cau_hoi>",
        ]
    )
    result = await llm.structured(
        agent="qa_filter", system=load_prompt("qa_filter", prompt_version), user=user, schema=QAFilter
    )
    canon = {p.casefold(): p for p in projects}
    result.project = canon.get(result.project.strip().casefold()) if result.project else None
    if not result.rewritten_query.strip():
        result.rewritten_query = question
    return result


def render_contexts(contexts: list[QAContext]) -> str:
    blocks = []
    for c in contexts:
        suffix = f" · {c.marker}" if c.marker else ""
        head = (
            f"[{c.ref}] ({c.meeting_date.strftime('%d/%m/%Y')} · {_safe(c.meeting_title)}"
            f" · {c.ts} · {_safe(c.speaker)}){suffix}"
        )
        blocks.append(f"{head}\n{_safe(c.text)}")
    return "\n\n".join(blocks)


async def answer_question(
    llm: LLMClient, *, question: str, contexts: list[QAContext], prompt_version: str
) -> QAAnswer:
    user = (
        f"<ngu_canh>\n{render_contexts(contexts)}\n</ngu_canh>\n\n<cau_hoi>{_safe(question)}</cau_hoi>"
    )
    return await llm.structured(
        agent="qa", system=load_prompt("qa", prompt_version), user=user, schema=QAAnswer
    )


def check_citations(answer: QAAnswer, contexts: list[QAContext]) -> tuple[str, list[QAContext]]:
    if answer.answer.strip().startswith(REFUSAL):
        return REFUSAL, []
    by_ref = {c.ref: c for c in contexts}
    candidates = [*answer.used_refs, *(int(m) for m in _MARKER.findall(answer.answer))]
    valid: list[int] = []
    for r in candidates:
        if r in by_ref and r not in valid:
            valid.append(r)
    if not valid:
        return REFUSAL, []

    def drop(m: re.Match[str]) -> str:
        return m.group(0) if int(m.group(1)) in by_ref else ""

    text = _MARKER.sub(drop, answer.answer)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r" +([.,;:!?])", r"\1", text)
    text = text.strip().lstrip(" .,;:!?")
    return text, [by_ref[r] for r in valid]
