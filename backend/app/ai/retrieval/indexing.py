"""Pure helpers that build the text to index: item search text and transcript chunks."""

from dataclasses import dataclass

from app.ai.domain.models import MeetingItem, Utterance

TYPE_LABELS = {
    "decision": "Quyết định",
    "action_item": "Việc cần làm",
    "blocker": "Vướng mắc",
    "request": "Yêu cầu",
    "open_question": "Câu hỏi mở",
    "knowledge": "Tri thức",
    "feedback": "Góp ý",
}


def item_search_text(item: MeetingItem) -> str:
    text = f"{TYPE_LABELS.get(item.type.value, item.type.value)}: {item.content}"
    if item.rationale:
        text += f". Lý do: {item.rationale}"
    if item.owner:
        text += f". Phụ trách: {item.owner}"
    return text


@dataclass
class ChunkSpec:
    seq: int
    start_ts: float
    end_ts: float | None
    first_utterance_id: str
    speakers: list[str]
    text: str


def make_transcript_chunks(
    utterances: list[Utterance], size: int = 6, overlap: int = 2
) -> list[ChunkSpec]:
    step = max(size - overlap, 1)
    chunks: list[ChunkSpec] = []
    start = 0
    while start < len(utterances):
        window = utterances[start : start + size]
        last = window[-1]
        chunks.append(
            ChunkSpec(
                seq=start,
                start_ts=window[0].start,
                end_ts=last.end if last.end is not None else last.start,
                first_utterance_id=window[0].id,
                speakers=list(dict.fromkeys(u.speaker for u in window)),
                text="\n".join(f"{u.speaker}: {u.text}" for u in window),
            )
        )
        if start + size >= len(utterances):
            break
        start += step
    return chunks
