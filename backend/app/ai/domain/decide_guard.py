"""Code-side checks on LLM dialogue-act labels before the state machine runs.

A DECIDE only counts for an option when its own quote names that option: the LLM must not fill in
the option of a bare "ok, chốt vậy nhé" from earlier context. Such a DECIDE keeps its act but loses
the option, so the state machine treats it as an unnamed decision (resolved only when exactly one
option is live, otherwise flagged for arbitration and human confirmation).
"""

import re
import unicodedata

from rapidfuzz import fuzz

from app.ai.domain.enums import Act
from app.ai.domain.models import DialogueAct

# Labels the LLM sometimes emits for "no option".
_NULL_LABELS = {"", "null", "none", "không", "khong"}
# Words that do not identify an option on their own.
_STOPWORDS = {
    "cho", "cua", "dung", "chon", "hay", "hoac", "la", "va", "voi", "the", "nao", "phuong", "an",
    "viec", "lam", "co", "khong", "mot", "cac", "nhung", "de", "tu", "trong", "theo",
}  # fmt: skip
_MATCH = 85


def _words(text: str) -> list[str]:
    s = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D")).casefold()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return [w.strip(".") for w in re.findall(r"[a-z0-9.]+", s) if w.strip(".")]


def _keywords(label: str) -> list[str]:
    return [
        w for w in _words(label)
        if w not in _STOPWORDS and (len(w) >= 3 or any(c.isdigit() for c in w))
    ]


def _same_word(a: str, b: str) -> bool:
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 4 and long_.startswith(short):  # "postgres" / "postgresql"
        return True
    return min(len(a), len(b)) >= 4 and fuzz.ratio(a, b) >= _MATCH


def mentions_option(quote: str, label: str) -> bool:
    """True when the quote names the option: a distinctive word of the label appears in it."""
    said = _words(quote)
    return any(_same_word(k, w) for k in _keywords(label) for w in said)


def guard_acts(acts: list[DialogueAct]) -> list[DialogueAct]:
    out = []
    for a in acts:
        option = a.option
        if option is not None and option.strip().casefold() in _NULL_LABELS:
            option = None
        if a.act == Act.DECIDE and option is not None and not mentions_option(a.quote, option):
            option = None
        out.append(a if option == a.option else a.model_copy(update={"option": option}))
    return out
