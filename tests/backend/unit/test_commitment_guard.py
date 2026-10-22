import pytest

from app.ai.domain.commitment_guard import (
    CONDITIONAL,
    DECLINED,
    NEGATION,
    TENTATIVE,
    WAITING,
    guard_items,
    is_conditional,
    is_tentative,
    release,
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
        ("Đúng, anh chưa quyết được khoản này.", True),
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


def test_a_bare_deferral_turned_into_asking_is_not_exempt() -> None:
    u = _utts(("Hằng", "Ừ, cái đó tính sau."),)
    item = _item(ItemType.ACTION_ITEM, u, [0], owner="Hằng")
    item = item.model_copy(update={"content": "Xin ý kiến: viết lại tài liệu API"})
    [out] = guard_items([item], u)
    assert NEEDS in out.flags and TENTATIVE in out.flags


def test_condition_cut_out_of_the_quote_is_still_seen() -> None:
    u = _utts(("Hằng", "Nếu bên pháp chế duyệt nội dung thì Vân soạn bộ mẫu thông báo tiếng Anh."),)
    item = _item(ItemType.ACTION_ITEM, u, [0], owner="Vân")
    ev = item.evidence[0].model_copy(update={"quote": "Vân soạn bộ mẫu thông báo tiếng Anh."})
    [out] = guard_items([item.model_copy(update={"evidence": [ev]})], u)
    assert NEEDS in out.flags and CONDITIONAL in out.flags
    assert out.condition == u[0].text


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


def test_hold_records_the_sentence_and_the_exact_phrase() -> None:
    u = _utts(("Hằng", "Quốc làm luôn dashboard nhé."),
              ("Quốc", "Tuần này em Kín lịch rồi chị, em không nhận thêm được đâu."))
    [out] = guard_items([_item(ItemType.ACTION_ITEM, u, [0], owner="Quốc")], u)
    assert out.hold is not None
    assert out.hold.reason == "declined" and out.hold.speaker == "Quốc"
    assert out.hold.phrase == "Kín lịch"  # as written, so the UI can highlight it
    assert out.hold.phrase in out.hold.quote
    assert [e.utterance_id for e in out.evidence] == [u[0].id, u[1].id]  # refusal is evidence


def test_condition_hold_highlights_the_if_clause_from_the_full_sentence() -> None:
    u = _utts(("Hằng", "Nếu bên pháp chế duyệt nội dung thì Vân soạn bộ mẫu."),)
    item = _item(ItemType.ACTION_ITEM, u, [0], owner="Vân")
    ev = item.evidence[0].model_copy(update={"quote": "Vân soạn bộ mẫu."})
    [out] = guard_items([item.model_copy(update={"evidence": [ev]})], u)
    assert out.hold is not None and out.hold.reason == "conditional"
    assert out.hold.phrase == "Nếu bên pháp chế duyệt nội dung thì"


def test_strongest_reason_is_the_hold_and_every_reason_is_a_flag() -> None:
    u = _utts(("Hằng", "Hay là nếu kịp thì Quốc làm dashboard nhé."),
              ("Quốc", "Em không kịp đâu chị."))
    [out] = guard_items([_item(ItemType.ACTION_ITEM, u, [0], owner="Quốc")], u)
    assert out.hold is not None and out.hold.reason == "declined"
    assert {TENTATIVE, CONDITIONAL, DECLINED} <= set(out.flags)


def test_no_owner_hold_without_a_phrase() -> None:
    u = _utts(("Hằng", "Cần cập nhật lại tài liệu cài đặt."),)
    [out] = guard_items([_item(ItemType.ACTION_ITEM, u, [0])], u)
    assert out.hold is not None and out.hold.reason == "no_owner" and out.hold.phrase is None


def test_official_items_have_no_hold() -> None:
    u = _utts(("Lan", "Minh dựng schema Postgres, xong trước thứ Sáu nhé."), ("Minh", "Vâng ạ."))
    [out] = guard_items([_item(ItemType.ACTION_ITEM, u, [0, 1], owner="Minh")], u)
    assert out.hold is None and out.flags == []


def test_negated_decision_with_a_positive_label_is_held() -> None:
    u = _utts(("Đạt", "Vậy mình chốt không mời Bách vào vòng ba."),)
    item = _item(ItemType.DECISION, u, [0], owner="Đạt").model_copy(
        update={"content": "Có mời Bách vào vòng 3 không? → Mời Bách vòng 3"})
    [out] = guard_items([item], u)
    assert out.hold is not None and out.hold.reason == "negation"
    assert out.hold.phrase == "chốt không" and NEGATION in out.flags and NEEDS in out.flags


def test_negated_decision_with_a_negative_label_is_fine() -> None:
    u = _utts(("Đạt", "Vậy mình chốt không mời Bách vào vòng ba."),)
    item = _item(ItemType.DECISION, u, [0], owner="Đạt").model_copy(
        update={"content": "Có mời Bách vào vòng 3 không? → Không mời Bách"})
    [out] = guard_items([item], u)
    assert out.hold is None and out.flags == []


def test_dropping_an_option_while_deciding_another_is_not_a_negation() -> None:
    u = _utts(("Hạnh", "Ok, vậy bỏ SendGrid, mình chốt Amazon SES."),)
    item = _item(ItemType.DECISION, u, [0], owner="Hạnh").model_copy(
        update={"content": "Chọn dịch vụ gửi email? → Amazon SES"})
    [out] = guard_items([item], u)
    assert out.hold is None


def test_release_makes_the_item_official() -> None:
    u = _utts(("Vân", "Hay là ai đó làm việc này."),)
    item = _item(ItemType.ACTION_ITEM, u, [0]).model_copy(update={"flags": ["missing_due_date"]})
    [held] = guard_items([item], u)
    out = release(held)
    assert out.hold is None and out.flags == ["missing_due_date"]
