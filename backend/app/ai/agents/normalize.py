"""Transcript normalization: glossary correction and chunking."""

import re

from pydantic import BaseModel
from rapidfuzz import fuzz

from app.ai.domain.models import Utterance

_TOKEN_RE = re.compile(r"\S+")
_EDGE_RE = re.compile(r"^(\W*)(.*?)(\W*)$", re.DOTALL)
_THRESHOLD = 90


class Chunk(BaseModel):
    index: int
    utterances: list[Utterance]


def _fix_text(text: str, terms: list[str]) -> str:
    tokens = list(_TOKEN_RE.finditer(text))
    out: list[str] = []
    pos = 0  # end offset already emitted
    i = 0
    while i < len(tokens):
        replaced = False
        for term in terms:
            n = len(term.split())
            if n == 0 or i + n > len(tokens):
                continue
            first, last = tokens[i], tokens[i + n - 1]
            window = text[first.start() : last.end()]
            edges = _EDGE_RE.match(window)
            assert edges is not None
            pre, core, post = edges.groups()
            if not core or core.lower() == term.lower():
                continue
            if fuzz.ratio(core.lower(), term.lower()) >= _THRESHOLD:
                out.append(text[pos : first.start()] + pre + term + post)
                pos = last.end()
                i += n
                replaced = True
                break
        if not replaced:
            i += 1
    out.append(text[pos:])
    return "".join(out)


def apply_glossary(utts: list[Utterance], glossary: list[str]) -> list[Utterance]:
    """Replace near-miss spellings of glossary terms (fuzz.ratio >= 90, not exact)."""
    terms = [t.strip() for t in glossary if t.strip()]
    return [u.model_copy(update={"text": _fix_text(u.text, terms)}) for u in utts]


def make_chunks(utts: list[Utterance], size: int = 40, overlap: int = 5) -> list[Chunk]:
    """Split utterances into windows of `size` sharing `overlap` utterances."""
    if size <= overlap:
        raise ValueError("size must be greater than overlap")
    chunks: list[Chunk] = []
    step = size - overlap
    start = 0
    while start < len(utts):
        chunks.append(Chunk(index=len(chunks), utterances=utts[start : start + size]))
        if start + size >= len(utts):
            break
        start += step
    return chunks
