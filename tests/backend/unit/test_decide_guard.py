import pytest

from app.ai.domain.decide_guard import guard_acts, mentions_option
from app.ai.domain.enums import Act
from app.ai.domain.models import DialogueAct


@pytest.mark.parametrize(
    ("quote", "label", "expected"),
    [
        ("Vậy mình chốt Postgres nhé.", "PostgreSQL", True),
        ("Ok, chốt React.", "React", True),
        ("Ok, chốt tăng pool lên 100.", "tăng kích thước pool", True),
        ("Ok, vậy bỏ SMS, mình chốt dùng Zalo ZNS cho OTP.", "Zalo ZNS", True),
        ("Vậy chốt nâng lên Python 3.13, nhưng chỉ khi thư viện PDF hỗ trợ.", "Python 3.13", True),
        ("Chốt, hạ ngưỡng cảnh báo xuống 70%.", "hạ ngưỡng cảnh báo", True),
        ("Ok chốt vậy nhé.", "S3 / ổ đĩa server", False),
        ("Ok chốt vậy nhé.", "Amazon S3", False),
        ("Ok, họp tới đây thôi.", "Figma", False),
        ("Hôm nay mình chốt CSDL cho dịch vụ thanh toán.", "PostgreSQL", False),
        ("Ok, chốt vậy.", "dùng", False),
    ],
)
def test_mentions_option(quote: str, label: str, expected: bool) -> None:
    assert mentions_option(quote, label) is expected


def _act(kind: Act, option: str | None, quote: str) -> DialogueAct:
    return DialogueAct(
        id="a1", utterance_id="u1", seq=1, speaker="Vy", start=1.0, act=kind, quote=quote,
        option=option,
    )


def test_unnamed_decide_loses_its_option() -> None:
    (a,) = guard_acts([_act(Act.DECIDE, "Amazon S3", "Ok chốt vậy nhé.")])
    assert a.option is None and a.act == Act.DECIDE


def test_named_decide_and_other_acts_keep_their_option() -> None:
    acts = [
        _act(Act.DECIDE, "Amazon S3", "Ok, chốt S3."),
        _act(Act.SUPPORT, "Amazon S3", "Em nghiêng về cái đó."),
    ]
    assert [a.option for a in guard_acts(acts)] == ["Amazon S3", "Amazon S3"]


@pytest.mark.parametrize("label", ["null", " None ", ""])
def test_null_labels_become_none(label: str) -> None:
    (a,) = guard_acts([_act(Act.REJECT, label, "Không mời Bách nữa.")])
    assert a.option is None
