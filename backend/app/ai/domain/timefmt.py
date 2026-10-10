"""Timestamp helpers: seconds <-> "hh:mm:ss" strings."""

import math
import re

_TS_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})(?:[,.](\d{1,3}))?$")


def fmt_ts(seconds: float) -> str:
    """Format seconds as "hh:mm:ss", rounding down to whole seconds."""
    total = math.floor(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_ts(s: str) -> float:
    """Parse "hh:mm:ss", "mm:ss", "hh:mm:ss,mmm" or "hh:mm:ss.mmm" into seconds.

    Raises:
        ValueError: If the string is not a valid timestamp.
    """
    match = _TS_RE.match(s.strip())
    if match is None:
        raise ValueError(f"invalid timestamp: {s!r}")
    hours_s, minutes_s, secs_s, frac = match.groups()
    minutes, secs = int(minutes_s), int(secs_s)
    if minutes >= 60 or secs >= 60:
        raise ValueError(f"invalid timestamp: {s!r}")
    hours = int(hours_s) if hours_s is not None else 0
    millis = int(frac.ljust(3, "0")) if frac is not None else 0
    return hours * 3600 + minutes * 60 + secs + millis / 1000
