"""Name normalisation helpers."""

import unicodedata


def norm_name(s: str) -> str:
    """NFC-normalise, casefold, collapse internal whitespace and strip."""
    return " ".join(unicodedata.normalize("NFC", s).casefold().split())
