from datetime import date

import pytest

from app.ai.domain.due_dates import resolve_due

D = date(2026, 10, 8)  # Thursday


@pytest.mark.parametrize(
    "text,expected",
    [
        ("thứ Sáu tuần sau", date(2026, 10, 16)),
        ("trước thứ 6 tuần sau", date(2026, 10, 16)),
        ("thứ Hai tuần này", date(2026, 10, 5)),
        ("thứ Sáu", date(2026, 10, 9)),
        ("thứ Năm", date(2026, 10, 15)),  # same weekday as meeting -> next week
        ("ngày mai", date(2026, 10, 9)),
        ("ngày kia", date(2026, 10, 10)),
        ("ngày mốt", date(2026, 10, 10)),
        ("3 ngày nữa", date(2026, 10, 11)),
        ("trong vòng 5 ngày nữa", date(2026, 10, 13)),
        ("trong vòng 5 ngày", date(2026, 10, 13)),
        ("trong 2 ngày tới", date(2026, 10, 10)),
        ("vòng 3 ngày", date(2026, 10, 11)),
        ("4 ngày tới", date(2026, 10, 12)),
        ("5 ngày", None),
        ("hôm nay", D),
        ("cuối tuần", date(2026, 10, 9)),
        ("cuối tuần sau", date(2026, 10, 16)),
        ("cuối tháng", date(2026, 10, 31)),
        ("20/10", date(2026, 10, 20)),
        ("05/01", date(2027, 1, 5)),
        ("20/10/2026", date(2026, 10, 20)),
        ("ngày 15/10", date(2026, 10, 15)),
        ("ngày 20/10/2026", date(2026, 10, 20)),
        ("ngày 25", date(2026, 10, 25)),
        ("ngày 3", date(2026, 11, 3)),
        ("bắt đầu từ tuần sau", None),
        ("sớm nhất có thể", None),
        (None, None),
        ("31/02", None),
        ("Chủ nhật tuần sau", date(2026, 10, 18)),
        ("thứ hai.", date(2026, 10, 12)),
    ],
)
def test_resolve_due(text, expected):
    assert resolve_due(text, D) == expected


def test_sunday_meeting_next_week():
    assert resolve_due("thứ Hai tuần sau", date(2026, 10, 11)) == date(2026, 10, 12)


@pytest.mark.parametrize("text", ["3000000 ngày nữa", "99999999999 ngày nữa"])
def test_huge_in_days_is_none(text):
    assert resolve_due(text, D) is None
