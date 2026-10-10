"""Verify that each dialogue act's quote really appears in its utterance."""

from rapidfuzz import fuzz

from app.ai.domain.models import DialogueAct, Utterance

_THRESHOLD = 90


def quote_matches(quote: str, text: str) -> bool:
    """True when ``quote`` fuzzily appears in ``text`` (casefolded partial match)."""
    return fuzz.partial_ratio(quote.casefold(), text.casefold()) >= _THRESHOLD


def check_quotes(
    acts: list[DialogueAct], utts: dict[str, Utterance]
) -> tuple[list[DialogueAct], float]:
    """Return (valid acts, invalid ratio). Comparison is casefolded."""
    if not acts:
        return [], 0.0
    valid: list[DialogueAct] = []
    for a in acts:
        u = utts.get(a.utterance_id)
        if u is None:
            continue
        if quote_matches(a.quote, u.text):
            valid.append(a)
    return valid, (len(acts) - len(valid)) / len(acts)
