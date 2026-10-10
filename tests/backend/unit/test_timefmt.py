import pytest

from app.ai.domain.timefmt import fmt_ts, parse_ts


def test_fmt_and_parse_ts():
    assert fmt_ts(2832.9) == "00:47:12"
    assert parse_ts("00:47:12") == 2832
    assert parse_ts("47:12") == 2832
    assert parse_ts("00:00:01,500") == 1.5
    with pytest.raises(ValueError):
        parse_ts("abc")
