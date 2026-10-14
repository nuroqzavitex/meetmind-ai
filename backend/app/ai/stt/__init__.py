"""Speech-to-text: diarized transcription and helpers that turn it into a "[hh:mm:ss] Name: text" transcript."""

import math
from typing import Any, Protocol

import openai
from pydantic import BaseModel

from app.ai.errors import STTError
from app.ai.parsing import parse_transcript

AUDIO_EXTENSIONS = (".mp3", ".m4a", ".wav", ".webm", ".mp4", ".mpeg", ".mpga")
LABEL_PREFIX = "Người nói"
MAX_SAMPLES = 3


class Segment(BaseModel):
    speaker: str
    start: float
    end: float | None = None
    text: str


class SpeechToText(Protocol):
    async def transcribe(self, filename: str, data: bytes) -> list[Segment]: ...


class OpenAISTT:
    """OpenAI diarizing transcription (`gpt-4o-transcribe-diarize`)."""

    def __init__(self, client: openai.AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    async def transcribe(self, filename: str, data: bytes) -> list[Segment]:
        try:
            result: Any = await self._client.audio.transcriptions.create(
                model=self._model,
                file=(filename, data),
                response_format="diarized_json",
                chunking_strategy="auto",
                stream=False,  # selects the SDK overload that types diarized_json
            )
        except openai.APIError as e:
            raise STTError(f"Lỗi OpenAI khi chuyển giọng nói: {e}") from e
        return [
            Segment(speaker=str(s.speaker), start=float(s.start), end=s.end, text=str(s.text))
            for s in (getattr(result, "segments", None) or [])
        ]


class FakeSTT:
    """Returns fixed segments; for tests."""

    def __init__(self, segments: list[Segment]) -> None:
        self._segments = segments

    async def transcribe(self, filename: str, data: bytes) -> list[Segment]:
        return list(self._segments)


class UnconfiguredSTT:
    """Stands in when no OpenAI key is set; fails only when a transcription is attempted."""

    async def transcribe(self, filename: str, data: bytes) -> list[Segment]:
        raise STTError("OPENAI_API_KEY chưa được cấu hình")


def is_audio(filename: str) -> bool:
    return filename.lower().endswith(AUDIO_EXTENSIONS)


def _label(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return f"{LABEL_PREFIX} {letters}"


def label_speakers(segments: list[Segment]) -> list[Segment]:
    """Rename raw diarization ids to "Người nói A, B, …" by first appearance; drop blank segments."""
    labels: dict[str, str] = {}
    out: list[Segment] = []
    for s in segments:
        text = " ".join(s.text.split())
        if not text:
            continue
        label = labels.setdefault(s.speaker, _label(len(labels)))
        out.append(s.model_copy(update={"speaker": label, "text": text}))
    return out


def _ts(seconds: float) -> str:
    millis = max(0, math.floor(seconds * 1000))
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def _lines(rows: list[tuple[float, str, str]]) -> bytes:
    return "".join(f"[{_ts(start)}] {speaker}: {text}\n" for start, speaker, text in rows).encode(
        "utf-8"
    )


def to_transcript_txt(segments: list[Segment]) -> bytes:
    return _lines([(s.start, s.speaker, s.text) for s in segments])


def rename_speakers(txt: bytes, mapping: dict[str, str]) -> bytes:
    """Rewrite speaker names of a generated transcript; unmapped names are kept."""
    utts = parse_transcript("transcript.txt", txt)
    return _lines([(u.start, mapping.get(u.speaker, u.speaker), u.text) for u in utts])


def speaker_summary(txt: bytes) -> list[tuple[str, int, list[str]]]:
    """(label, utterance count, first samples) per speaker, in order of first appearance."""
    counts: dict[str, int] = {}
    samples: dict[str, list[str]] = {}
    for u in parse_transcript("transcript.txt", txt):
        counts[u.speaker] = counts.get(u.speaker, 0) + 1
        bucket = samples.setdefault(u.speaker, [])
        if len(bucket) < MAX_SAMPLES:
            bucket.append(u.text)
    return [(name, counts[name], samples[name]) for name in counts]


__all__ = [
    "AUDIO_EXTENSIONS",
    "FakeSTT",
    "OpenAISTT",
    "Segment",
    "SpeechToText",
    "UnconfiguredSTT",
    "is_audio",
    "label_speakers",
    "rename_speakers",
    "speaker_summary",
    "to_transcript_txt",
]
