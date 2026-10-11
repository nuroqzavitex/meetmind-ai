from typing import Any

from app.ai.domain.enums import ItemType
from app.ai.domain.models import Evidence, MeetingItem, Utterance
from app.ai.retrieval.indexing import item_search_text, make_transcript_chunks


def _item(**kw: Any) -> MeetingItem:
    base: dict[str, Any] = {
        "id": "i1",
        "meeting_id": "m1",
        "type": ItemType.DECISION,
        "content": "Dùng PostgreSQL → Postgres",
        "evidence": [Evidence(utterance_id="u0", speaker="Lan", ts="00:00:01", quote="q")],
    }
    base.update(kw)
    return MeetingItem(**base)


def test_search_text_full() -> None:
    item = _item(rationale="ACID", owner="Lan")
    assert (
        item_search_text(item)
        == "Quyết định: Dùng PostgreSQL → Postgres. Lý do: ACID. Phụ trách: Lan"
    )


def test_search_text_minimal() -> None:
    assert item_search_text(_item()) == "Quyết định: Dùng PostgreSQL → Postgres"


def test_search_text_other_label() -> None:
    assert item_search_text(_item(type=ItemType.ACTION_ITEM)).startswith("Việc cần làm: ")


def _utts(n: int) -> list[Utterance]:
    return [
        Utterance(
            id=f"u{i}",
            seq=i,
            speaker="Lan" if i % 2 else "Minh",
            start=i * 10.0,
            end=i * 10.0 + 5,
            text=f"câu {i}",
        )
        for i in range(n)
    ]


def test_chunk_windows() -> None:
    chunks = make_transcript_chunks(_utts(16))
    assert [c.seq for c in chunks] == [0, 4, 8, 12]
    assert [c.text.count("\n") + 1 for c in chunks] == [6, 6, 6, 4]
    assert [c.first_utterance_id for c in chunks] == ["u0", "u4", "u8", "u12"]
    assert chunks[0].speakers == ["Minh", "Lan"]
    assert chunks[0].start_ts == 0.0 and chunks[0].end_ts == 55.0
    assert chunks[0].text.splitlines()[0] == "Minh: câu 0"


def test_chunks_empty_and_short() -> None:
    assert make_transcript_chunks([]) == []
    assert len(make_transcript_chunks(_utts(3))) == 1
