"""Transcript parsers: choose a parser by file extension."""

from app.ai.domain.models import Utterance
from app.ai.errors import TranscriptParseError
from app.ai.parsing.docx import parse_docx
from app.ai.parsing.srt import parse_srt
from app.ai.parsing.txt import parse_txt
from app.ai.parsing.vtt import parse_vtt

_PARSERS = {".txt": parse_txt, ".srt": parse_srt, ".vtt": parse_vtt, ".docx": parse_docx}


def parse_transcript(filename: str, data: bytes) -> list[Utterance]:
    """Parse transcript bytes into utterances.

    Raises:
        TranscriptParseError: Unknown extension, undecodable content or no utterances.
    """
    name = filename.lower()
    dot = name.rfind(".")
    parser = _PARSERS.get(name[dot:]) if dot >= 0 else None
    if parser is None:
        raise TranscriptParseError(f"unsupported transcript format: {filename!r}")
    utts = parser(data)
    if not utts:
        raise TranscriptParseError(f"no utterances found in {filename!r}")
    return utts


__all__ = ["parse_transcript"]
