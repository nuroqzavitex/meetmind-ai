import pytest

from app.ai.domain.commitment_guard import (
    CONDITIONAL,
    DECLINED,
    TENTATIVE,
    WAITING,
    guard_items,
    is_conditional,
    is_tentative,
)
from app.ai.domain.enums import ItemType
from app.ai.domain.models import Evidence, MeetingItem, Utterance

NEEDS = "needs_confirmation"


def _utts(*lines: tuple[str, str]) -> list[Utterance]:
    return [
        Utterance(id=f"u{i:04d}", seq=i, speaker=s, start=float(i * 10), text=t)
        for i, (s, t) in enumerate(lines)
    ]


def _item(kind: ItemType, utts: list[Utterance], ids: list[int], owner: str | None = None,
          condition: str | None = None) -> MeetingItem:
    return MeetingItem(
        id="i1", meeting_id="m", type=kind, content="x", owner=owner, condition=condition,
        evidence=[
            Evidence(utterance_id=utts[i].id, speaker=utts[i].speaker, ts="00:00:00",
                     quote=utts[i].text)
            for i in ids
        ],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hay là ai đó viết lại tài liệu API nhỉ.", True),
        ("Chắc là dùng bộ icon cũ thôi.", True),
        ("Có lẽ vậy, để chị xem lại đã.", True),
        ("Ừ, cái đó tính sau.", True),
        ("Tạm chốt Redis, tuần sau xem lại.", True),
        ("Minh dựng schema Postgres, xong trước thứ Sáu nhé.", False),
        ("Ok, chốt Redis Streams cho hàng đợi.", False),
        ("Em chắc chắn làm kịp.", False),  # "chắc chắn" is firm, not "chắc là"
    ],
)
def test_is_tentative(text: str, expected: bool) -> None:
    assert is_tentative(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Nếu pháp chế đồng ý thì Vân soạn bộ mẫu.", True),
        ("Chốt Python 3.13, nhưng chỉ khi thư viện PDF hỗ trợ.", True),
        ("Trong trường hợp khách đổi ý, Hà sửa hợp đồng.", True),
        ("Hà sửa hợp đồng trong hôm nay.", False),
    ],
)
def test_is_conditional(text: str, expected: bool) -> None:
    assert is_conditional(text) is expected


def test_firm_assignment_stays_official() -> None:
    u = _utts(("Hằng", "Quốc dựng hàng đợi Redis Streams, xong trước thứ Năm nhé."),
              ("Quốc", "Dạ, em nhận."))
    [out] = guard_items([_item(ItemType.ACTION_ITEM, u, [0, 1], owner="Quốc")], u)
    assert out.flags == []


def test_suggestion_without_taker_needs_confirmation() -> None:
    u = _utts(("Vân", "Hay là ai đó viết lại tài liệu API cho đội mobile nhỉ."),
              ("Hằng", "Ừ, cái đó tính sau."))
    [out] = guard_items([_item(ItemType.ACTION_ITEM, u, [0], owner="ai đó")], u)
    assert out.owner is None  # "ai đó" is nobody
    assert NEEDS in out.flags and TENTATIVE in out.flags


def test_suggestion_taken_by_someone_is_official() -> None:
    u = _utts(("Vân", "Hay là ai đó viết lại tài liệu API nhỉ."),
              ("Tú", "Để em làm, thứ Sáu em gửi."))
    [out] = guard_items([_item(ItemType.ACTION_ITEM, u, [0, 1], owner="Tú")], u)
    assert out.flags == []


def test_conditional_task_keeps_its_condition() -> None:
    u = _utts(("Hằng", "Nếu bên pháp chế đồng ý nội dung thì Vân soạn bộ mẫu thông báo tiếng Anh."),)
    [out] = guard_items([_item(ItemType.ACTION_ITEM, u, [0], owner="Vân")], u)
    assert NEEDS in out.flags and CONDITIONAL in out.flags
    assert out.condition == u[0].text


def test_declined_by_the_assignee_needs_confirmation() -> None:
    u = _utts(("Hằng", "Quốc làm luôn dashboard theo dõi tỉ lệ gửi thành công nhé."),
              ("Quốc", "Tuần này em kín lịch rồi chị, em không nhận thêm được đâu."))
    [out] = guard_items([_item(ItemType.ACTION_ITEM, u, [0], owner="Quốc")], u)
    assert NEEDS in out.flags and DECLINED in out.flags


def test_someone_else_objecting_does_not_count_as_declining() -> None:
    u = _utts(("Hằng", "Quốc làm dashboard nhé."),
              ("Vân", "Em thì không kịp đâu, may mà không phải em."))
    [out] = guard_items([_item(ItemType.ACTION_ITEM, u, [0], owner="Quốc")], u)
    assert out.flags == []


def test_decline_far_after_the_assignment_is_ignored() -> None:
    u = _utts(("Hằng", "Quốc làm dashboard nhé."), ("Vân", "a"), ("Tú", "b"), ("Hằng", "c"),
              ("Quốc", "Báo cáo kia thì em không kịp."))
    [out] = guard_items([_item(ItemType.ACTION_ITEM, u, [0], owner="Quốc")], u)
    assert out.flags == []


def test_waiting_for_news_is_not_a_task() -> None:
    u = _utts(("Nhi", "Dạ, vậy em chờ tin từ Long."),)
    [out] = guard_items([_item(ItemType.ACTION_ITEM, u, [0], owner="Nhi")], u)
    assert NEEDS in out.flags and WAITING in out.flags


def test_asking_for_an_opinion_is_a_commitment_despite_the_doubt() -> None:
    u = _utts(("Đạt", "Cái này anh chưa chắc, để anh xin ý kiến chị giám đốc nhân sự rồi báo lại."),)
    item = _item(ItemType.ACTION_ITEM, u, [0], owner="Đạt")
    item = item.model_copy(update={"content": "Xin ý kiến: mức lương cho vị trí mới"})
    [out] = guard_items([item], u)
    assert out.flags == []


def test_task_without_owner_needs_confirmation() -> None:
    u = _utts(("Hằng", "Cần cập nhật lại tài liệu cài đặt."),)
    [out] = guard_items([_item(ItemType.ACTION_ITEM, u, [0])], u)
    assert out.flags == [NEEDS]


def test_tentative_decision_needs_confirmation() -> None:
    u = _utts(("Hằng", "Có lẽ dùng bộ icon cũ, để chị xem lại đã."),)
    [out] = guard_items([_item(ItemType.DECISION, u, [0], owner="Hằng")], u)
    assert NEEDS in out.flags and TENTATIVE in out.flags


def test_conditional_decision_is_marked_but_stays_a_decision() -> None:
    u = _utts(("Trang", "Vậy chốt nâng lên Python 3.13, nhưng chỉ khi thư viện PDF hỗ trợ."),)
    item = _item(ItemType.DECISION, u, [0], owner="Trang", condition="thư viện PDF hỗ trợ")
    [out] = guard_items([item], u)
    assert out.flags == [CONDITIONAL] and out.condition == "thư viện PDF hỗ trợ"


def test_firm_decision_and_other_types_are_untouched() -> None:
    u = _utts(("Lan", "Vậy mình chốt Postgres nhé."), ("Hoa", "Có lẽ staging hỏng do ổ đĩa."))
    items = [_item(ItemType.DECISION, u, [0], owner="Lan"), _item(ItemType.BLOCKER, u, [1])]
    assert [i.flags for i in guard_items(items, u)] == [[], []]


def test_flags_are_not_duplicated() -> None:
    u = _utts(("Vân", "Hay là ai đó làm việc này."),)
    item = _item(ItemType.ACTION_ITEM, u, [0]).model_copy(update={"flags": [NEEDS]})
    [out] = guard_items([item], u)
    assert out.flags.count(NEEDS) == 1
