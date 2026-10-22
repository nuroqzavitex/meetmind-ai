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
# Why an item was not settled (MeetingItem.hold), worded for the Q&A answer.
HOLD_LABELS = {
    "declined": "người được giao đã từ chối",
    "conditional": "chỉ làm khi có điều kiện",
    "negation": "câu chốt mang ý phủ định",
    "waiting": "chỉ là chờ phản hồi",
    "tentative": "mới là gợi ý, chưa ai cam kết",
    "no_owner": "chưa có người nhận",
}


def item_search_text(item: MeetingItem) -> str:
    text = f"{TYPE_LABELS.get(item.type.value, item.type.value)}: {item.content}"
    if item.rationale:
        text += f". Lý do: {item.rationale}"
    if item.owner:
        text += f". Phụ trách: {item.owner}"
    if item.hold:
        h = item.hold
        who = f"{h.speaker} ({h.ts})" if h.speaker and h.ts else (h.speaker or "")
        text += f". Chưa chốt vì {HOLD_LABELS[h.reason]}: {who} nói \"{h.quote}\""
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
