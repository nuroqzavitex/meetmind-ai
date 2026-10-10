"""Plain-text transcript parser: "[hh:mm:ss] Name: text"."""

from app.ai.domain.models import Utterance
from app.ai.parsing._common import decode, parse_bracket_lines


def parse_txt(data: bytes) -> list[Utterance]:
    return parse_bracket_lines(decode(data).splitlines())
