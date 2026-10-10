"""Shared helpers for transcript parsers."""

import re
import unicodedata

from app.ai.domain.models import Utterance
from app.ai.domain.timefmt import parse_ts
from app.ai.errors import TranscriptParseError

UNKNOWN_SPEAKER = "Unknown"

_LINE_RE = re.compile(r"^\[(?P<ts>[^\]]+)\]\s*(?P<rest>.*)$")
_SPEAKER_RE = re.compile(r"^(?P<name>[^\W\d][^:\n]{0,39}?)\s*:\s+(?P<text>.+)$")


def split_speaker(text: str) -> tuple[str, str]:
    """Split a "Name: content" prefix; speaker is "Unknown" when absent."""
    match = _SPEAKER_RE.match(text.strip())
    if match is None:
        return UNKNOWN_SPEAKER, text.strip()
    return match.group("name").strip(), match.group("text").strip()


def decode(data: bytes) -> str:
    """Decode UTF-8 (BOM tolerated) to NFC text or raise TranscriptParseError."""
    try:
        return unicodedata.normalize("NFC", data.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise TranscriptParseError("transcript is not valid UTF-8") from exc


def parse_bracket_lines(lines: list[str]) -> list[Utterance]:
    """Parse "[hh:mm:ss] Name: text" lines; unstamped lines continue the previous one."""
    entries: list[tuple[float, str, str]] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        match = _LINE_RE.match(line)
        start: float | None = None
        if match is not None:
            try:
                start = parse_ts(match.group("ts"))
            except ValueError:
                start = None
        if match is not None and start is not None:
            speaker, text = split_speaker(match.group("rest"))
            entries.append((start, speaker, text))
        elif entries:
            start0, speaker, text = entries[-1]
            entries[-1] = (start0, speaker, f"{text} {line}".strip())
    return [
        Utterance(
            id=f"u{i:04d}",
            seq=i,
            speaker=speaker,
            start=start,
            end=entries[i + 1][0] if i + 1 < len(entries) else None,
            text=text,
        )
        for i, (start, speaker, text) in enumerate(entries)
    ]


def build_cues(cues: list[tuple[float, float, str, str | None]]) -> list[Utterance]:
    """Build utterances from (start, end, text, explicit_speaker) cues."""
    utts: list[Utterance] = []
    for start, end, text, voice in cues:
        speaker, body = (voice, text.strip()) if voice else split_speaker(text)
        utts.append(
            Utterance(
                id=f"u{len(utts):04d}",
                seq=len(utts),
                speaker=speaker,
                start=start,
                end=end,
                text=body,
            )
        )
    return utts
