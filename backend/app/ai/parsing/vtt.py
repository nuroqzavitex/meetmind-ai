"""WebVTT transcript parser (supports voice tags like <v Name>)."""

import re

from app.ai.domain.models import Utterance
from app.ai.domain.timefmt import parse_ts
from app.ai.parsing._common import build_cues, decode

_TIME_RE = re.compile(r"^\s*(\S+)\s*-->\s*(\S+)")
_VOICE_RE = re.compile(r"<v(?:\.[^\s>]*)?\s+([^>]+)>")
_TAG_RE = re.compile(r"</?[^>]+>")


def parse_vtt(data: bytes) -> list[Utterance]:
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
            raw = " ".join(ln.strip() for ln in lines[idx + 1 :])
            voice_match = _VOICE_RE.search(raw)
            voice = voice_match.group(1).strip() if voice_match else None
            text = _TAG_RE.sub("", raw).strip()
            if text:
                cues.append((start, end, text, voice))
            break
    return build_cues(cues)
