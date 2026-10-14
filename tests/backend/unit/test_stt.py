from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest

from app.ai.errors import STTError
from app.ai.parsing import parse_transcript
from app.ai.stt import (
    FakeSTT,
    OpenAISTT,
    Segment,
    UnconfiguredSTT,
    is_audio,
    label_speakers,
    rename_speakers,
    speaker_summary,
    to_transcript_txt,
)

SEGS = [
    Segment(speaker="spk_7", start=1.2, end=3.0, text=" Chào mọi người "),
    Segment(speaker="spk_2", start=3.5, end=5.0, text="Em đề xuất MongoDB"),
    Segment(speaker="spk_7", start=5.25, end=7.0, text="Vậy chốt Postgres nhé"),
    Segment(speaker="spk_2", start=7.5, end=8.0, text="   "),
]


@pytest.mark.parametrize(
    ("name", "expected"),
    [("hop.MP3", True), ("a.m4a", True), ("a.wav", True), ("a.webm", True), ("a.mp4", True),
     ("a.mpeg", True), ("a.mpga", True), ("a.txt", False), ("a.vtt", False), ("mp3", False)],
)
def test_is_audio(name: str, expected: bool) -> None:
    assert is_audio(name) is expected


def test_label_speakers_by_first_appearance_and_drops_blank_text() -> None:
    out = label_speakers(SEGS)
    assert [s.speaker for s in out] == ["Người nói A", "Người nói B", "Người nói A"]
    assert out[0].text == "Chào mọi người"


def test_transcript_txt_round_trips_through_the_txt_parser() -> None:
    txt = to_transcript_txt(label_speakers(SEGS))
    assert txt.decode("utf-8").splitlines()[0] == "[00:00:01.200] Người nói A: Chào mọi người"
    utts = parse_transcript("x.txt", txt)
    assert [(u.speaker, u.text) for u in utts] == [
        ("Người nói A", "Chào mọi người"),
        ("Người nói B", "Em đề xuất MongoDB"),
        ("Người nói A", "Vậy chốt Postgres nhé"),
    ]
    assert utts[2].start == pytest.approx(5.25)


def test_speaker_summary_counts_and_samples() -> None:
    txt = to_transcript_txt(label_speakers(SEGS))
    assert speaker_summary(txt) == [
        ("Người nói A", 2, ["Chào mọi người", "Vậy chốt Postgres nhé"]),
        ("Người nói B", 1, ["Em đề xuất MongoDB"]),
    ]


def test_speaker_summary_keeps_at_most_three_samples() -> None:
    segs = [Segment(speaker="x", start=float(i), end=None, text=f"câu {i}") for i in range(5)]
    assert speaker_summary(to_transcript_txt(label_speakers(segs)))[0][2] == ["câu 0", "câu 1", "câu 2"]


def test_rename_speakers_rewrites_every_line() -> None:
    txt = to_transcript_txt(label_speakers(SEGS))
    renamed = rename_speakers(txt, {"Người nói A": "Lan", "Người nói B": "Minh"})
    utts = parse_transcript("x.txt", renamed)
    assert [u.speaker for u in utts] == ["Lan", "Minh", "Lan"]
    assert utts[1].text == "Em đề xuất MongoDB"


async def test_fake_stt_returns_segments() -> None:
    assert await FakeSTT(SEGS).transcribe("a.mp3", b"x") == SEGS


async def test_unconfigured_stt_raises() -> None:
    with pytest.raises(STTError, match="OPENAI_API_KEY"):
        await UnconfiguredSTT().transcribe("a.mp3", b"x")


class StubOpenAI:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.kwargs: dict[str, Any] = {}

        async def create(**kwargs: Any) -> Any:
            self.kwargs = kwargs
            if error is not None:
                raise error
            return result

        self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=create))


async def test_openai_stt_requests_diarized_json() -> None:
    result = SimpleNamespace(
        segments=[SimpleNamespace(speaker="A", start=0.0, end=1.5, text="Xin chào")]
    )
    stub = StubOpenAI(result)
    out = await OpenAISTT(stub, "gpt-4o-transcribe-diarize").transcribe("hop.m4a", b"audio")  # type: ignore[arg-type]
    assert out == [Segment(speaker="A", start=0.0, end=1.5, text="Xin chào")]
    assert stub.kwargs["model"] == "gpt-4o-transcribe-diarize"
    assert stub.kwargs["response_format"] == "diarized_json"
    assert stub.kwargs["chunking_strategy"] == "auto"
    assert stub.kwargs["file"] == ("hop.m4a", b"audio")


async def test_openai_stt_api_error_becomes_stt_error() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")
    stub = StubOpenAI(error=openai.APIConnectionError(request=request))
    with pytest.raises(STTError, match="OpenAI"):
        await OpenAISTT(stub, "m").transcribe("a.mp3", b"x")  # type: ignore[arg-type]
