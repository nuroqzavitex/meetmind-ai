"""DOCX transcript parser: each paragraph is treated as one .txt line."""

import io
import unicodedata

from docx import Document

from app.ai.domain.models import Utterance
from app.ai.errors import TranscriptParseError
from app.ai.parsing._common import parse_bracket_lines


def parse_docx(data: bytes) -> list[Utterance]:
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise TranscriptParseError("cannot read docx file") from exc
    return parse_bracket_lines([unicodedata.normalize("NFC", p.text) for p in document.paragraphs])
