"""SRT subtitle transcript parser."""

import re

from app.ai.domain.models import Utterance
from app.ai.domain.timefmt import parse_ts
from app.ai.parsing._common import build_cues, decode

_TIME_RE = re.compile(r"^\s*(\S+)\s*-->\s*(\S+)")


def parse_srt(data: bytes) -> list[Utterance]:
    cues: list[tuple[float, float, str, str | None]] = []
    for block in re.split(r"\n\s*\n", decode(data).replace("\r\n", "\n").replace("\r", "\n")):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        for idx, line in enumerate(lines):
            match = _TIME_RE.match(line)
            if match is None:
                continue
            try:
                start, end = parse_ts(match.group(1)), parse_ts(match.group(2))
            except ValueError:
                break
            text = " ".join(ln.strip() for ln in lines[idx + 1 :])
            if text:
                cues.append((start, end, text, None))
            break
    return build_cues(cues)
