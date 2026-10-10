"""Golden models and greedy matching of predicted items to golden items."""

import unicodedata
from datetime import date
from typing import Literal

from pydantic import BaseModel, model_validator
from rapidfuzz import fuzz

from app.ai.domain.enums import ItemType
from app.ai.domain.models import MeetingContext, MeetingItem


class GoldTopic(BaseModel):
    question: str
    final_option: str | None
    match: list[str]  # identifies decisions of this topic (question and option words)
    final_match: list[str] = []  # words of the final option only

    @model_validator(mode="after")
    def _final_match_required(self) -> "GoldTopic":
        if self.final_option is not None and not self.final_match:
            raise ValueError("final_match must be non-empty when final_option is set")
        return self


class GoldItem(BaseModel):
    type: ItemType
    content: str
    match: list[str]
    owner: str | None = None
    due_date: date | None = None
    status: str | None = None


class Golden(BaseModel):
    context: MeetingContext
    transcript: str
    kind: Literal["realistic", "trap"]
    topics: list[GoldTopic]
    items: list[GoldItem]


def strip_accents(s: str) -> str:
    """Casefold, drop diacritics (and map d-stroke to d)."""
    s = s.casefold().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", s)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def contains_keyword(text: str, keywords: list[str]) -> bool:
    t = strip_accents(text)
    return any(strip_accents(k) in t for k in keywords)


def decision_label(content: str) -> str:
    """Option part of a "{question} → {label}" decision; whole content if no arrow."""
    return content.rsplit("→", 1)[-1]


def _keyword_text(item: MeetingItem) -> str:
    return decision_label(item.content) if item.type == ItemType.DECISION else item.content


def match_items(pred: list[MeetingItem], gold: list[GoldItem]) -> list[tuple[int, int]]:
    """Greedy one-to-one matching: same type + a keyword hit, best token_set_ratio first.

    Decision keywords are option words, so they are checked against the option label only.
    """
    cands: list[tuple[float, int, int]] = []
    for pi, p in enumerate(pred):
        for gi, g in enumerate(gold):
            if p.type == g.type and contains_keyword(_keyword_text(p), g.match):
                score = fuzz.token_set_ratio(strip_accents(p.content), strip_accents(g.content))
                cands.append((score, pi, gi))
    cands.sort(key=lambda c: (-c[0], c[1], c[2]))
    used_p: set[int] = set()
    used_g: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for _, pi, gi in cands:
        if pi in used_p or gi in used_g:
            continue
        used_p.add(pi)
        used_g.add(gi)
        pairs.append((pi, gi))
    return sorted(pairs)
