"""Resolve Vietnamese relative due-date phrases against a meeting date."""

import calendar
import re
import unicodedata
from datetime import date, timedelta

_WEEKDAYS = {
    "2": 0, "hai": 0, "3": 1, "ba": 1, "4": 2, "tư": 2, "5": 3, "năm": 3,
    "6": 4, "sáu": 4, "7": 5, "bảy": 5, "chủ nhật": 6, "cn": 6,
}  # fmt: skip

_PREFIX = re.compile(r"^(?:(?:trước khi hết|trước|hạn chót|hạn|deadline)\s*[:\-]?\s*)+")
_WEEKDAY = re.compile(
    r"(?<!\w)(?:thứ\s+(2|3|4|5|6|7|hai|ba|tư|năm|sáu|bảy)|(chủ nhật|cn))"
    r"(?:\s+tuần\s+(này|sau|tới))?$"
)
_END_WEEK = re.compile(r"cuối tuần(?:\s+(này|sau|tới))?$")
_IN_DAYS = re.compile(r"(\d+)\s+ngày\s+nữa$")
_DATE = re.compile(r"(?:ngày\s+)?(\d{1,2})/(\d{1,2})(?:/(\d{4}))?$")
_DAY_ONLY = re.compile(r"ngày\s+(\d{1,2})$")
_FIXED = {
    "hôm nay": 0,
    "ngày mai": 1,
    "ngày kia": 2,
    "ngày mốt": 2,
}


def _normalize(text: str) -> str:
    s = unicodedata.normalize("NFC", text).casefold().strip()
    s = re.sub(r"\s+", " ", s).rstrip(" .,;:!?")
    return _PREFIX.sub("", s).strip()


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def resolve_due(due_text: str | None, meeting_date: date) -> date | None:
    """Return the absolute due date for ``due_text``, or None if unrecognised."""
    if not due_text:
        return None
    s = _normalize(due_text)
    if not s or "bắt đầu" in s:
        return None

    monday = meeting_date - timedelta(days=meeting_date.weekday())

    if s in _FIXED:
        return meeting_date + timedelta(days=_FIXED[s])

    if m := _IN_DAYS.match(s):
        try:
            return meeting_date + timedelta(days=int(m.group(1)))
        except (OverflowError, ValueError):
            return None

    if m := _END_WEEK.match(s):
        week = monday + timedelta(days=7 if m.group(1) in ("sau", "tới") else 0)
        return week + timedelta(days=4)

    if s == "cuối tháng":
        last = calendar.monthrange(meeting_date.year, meeting_date.month)[1]
        return date(meeting_date.year, meeting_date.month, last)

    if m := _WEEKDAY.search(s):
        wd = _WEEKDAYS[m.group(1) or m.group(2)]
        rel = m.group(3)
        if rel is None:
            delta = (wd - meeting_date.weekday()) % 7 or 7
            return meeting_date + timedelta(days=delta)
        return monday + timedelta(days=wd + (7 if rel in ("sau", "tới") else 0))

    if m := _DATE.match(s):
        day, month = int(m.group(1)), int(m.group(2))
        if m.group(3):
            return _safe_date(int(m.group(3)), month, day)
        year = meeting_date.year
        for y in (year, year + 1):
            cand = _safe_date(y, month, day)
            if cand and cand >= meeting_date:
                return cand
        return None

    if m := _DAY_ONLY.match(s):
        day = int(m.group(1))
        y, mo = meeting_date.year, meeting_date.month
        for _ in range(13):
            cand = _safe_date(y, mo, day)
            if cand and cand >= meeting_date:
                return cand
            mo += 1
            if mo > 12:
                mo, y = 1, y + 1
        return None

    return None
