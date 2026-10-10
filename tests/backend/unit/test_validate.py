from datetime import date

from app.ai.agents.validate import validate_items
from app.ai.domain.enums import ItemType
from app.ai.domain.models import Evidence, MeetingItem


def ev(n: int = 1, ts: str = "00:00:10") -> Evidence:
    return Evidence(utterance_id=f"u{n}", speaker="Minh", ts=ts, quote=f"q{n}")


def mk(kind: ItemType, content: str = "noi dung", conf: float = 0.8, evidence=None, **kw):
    return MeetingItem(
        id=kw.pop("id", ""), meeting_id="m1", type=kind, content=content,
        confidence=conf, evidence=[ev()] if evidence is None else evidence, **kw,
    )


def ai(owner="Lan", due=date(2026, 10, 9), **kw):
    return mk(ItemType.ACTION_ITEM, owner=owner, due_date=due, **kw)


def dec(conf=0.8, owner="Lan", **kw):
    return mk(ItemType.DECISION, conf=conf, owner=owner, **kw)


def test_action_item_missing_fields_flagged():
    out = validate_items([ai(owner=None, due=None)])
    assert set(out[0].flags) == {"missing_owner", "missing_due_date"}


def test_decision_missing_owner_and_request_missing_requester():
    assert validate_items([dec(owner=None)])[0].flags == ["missing_owner"]
    assert validate_items([mk(ItemType.REQUEST)])[0].flags == ["missing_requester"]
    assert validate_items([mk(ItemType.BLOCKER)])[0].flags == []


def test_low_confidence_threshold():
    assert "low_confidence" in validate_items([dec(conf=0.59)])[0].flags
    assert "low_confidence" not in validate_items([dec(conf=0.6)])[0].flags


def test_item_without_evidence_dropped():
    assert validate_items([dec(evidence=[])]) == []


def test_existing_flag_not_duplicated():
    out = validate_items([dec(owner=None, flags=["missing_owner"])])
    assert out[0].flags == ["missing_owner"]


def test_duplicates_merged():
    a = dec(content="Dùng Postgres cho DB", conf=0.7, evidence=[ev(1)], flags=["x"], id="a")
    b = dec(content="dùng postgres cho db", conf=0.9, evidence=[ev(1), ev(2, "00:00:20")],
            flags=["y", "x"], id="b")
    out = validate_items([a, b])
    assert len(out) == 1
    assert out[0].id == "b"
    assert [e.utterance_id for e in out[0].evidence] == ["u1", "u2"]
    assert out[0].flags == ["y", "x"]


def test_duplicate_tie_keeps_earlier_and_appends_evidence():
    a = dec(content="same thing", evidence=[ev(1)], flags=["x"], id="a")
    b = dec(content="same thing", evidence=[ev(2)], flags=["y"], id="b")
    out = validate_items([a, b])
    assert [i.id for i in out] == ["a"]
    assert [e.utterance_id for e in out[0].evidence] == ["u1", "u2"]
    assert out[0].flags == ["x", "y"]


def test_different_type_not_merged():
    out = validate_items([dec(content="same thing"), mk(ItemType.BLOCKER, content="same thing")])
    assert len(out) == 2


def test_flagged_items_sorted_first_then_by_ts():
    clean_early = dec(id="c1", evidence=[ev(1, "00:00:05")], content="alpha beta")
    clean_late = dec(id="c2", evidence=[ev(2, "00:01:00")], content="gamma delta")
    flagged_late = dec(id="f1", owner=None, evidence=[ev(3, "00:02:00")], content="epsilon zeta")
    flagged_early = dec(id="f2", conf=0.3, evidence=[ev(4, "00:00:30")], content="eta theta")
    out = validate_items([clean_late, flagged_late, clean_early, flagged_early])
    assert [i.id for i in out] == ["f2", "f1", "c1", "c2"]


def test_inputs_not_mutated():
    item = ai(owner=None, due=None)
    validate_items([item])
    assert item.flags == []


def test_subset_action_items_with_different_owners_not_merged():
    a = ai(owner="Minh", content="Viết test", evidence=[ev(1)])
    b = ai(owner="Hoa", content="Viết test cho API thanh toán", evidence=[ev(2)])
    assert len(validate_items([a, b])) == 2


def test_action_item_duplicates_need_same_owner():
    a = ai(owner="Minh", content="Viết test cho API thanh toán", evidence=[ev(1)])
    same = ai(owner=" minh ", content="viết test cho API thanh toán", evidence=[ev(2)])
    other = ai(owner="Hoa", content="Viết test cho API thanh toán", evidence=[ev(3)])
    none_a = ai(owner=None, content="Dựng schema DB", evidence=[ev(4)])
    none_b = ai(owner=None, content="dựng schema db", evidence=[ev(5)])
    out = validate_items([a, same, other, none_a, none_b])
    assert len(out) == 3
