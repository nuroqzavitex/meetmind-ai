"""Agent 4: validate MeetingItems - flag gaps, drop unsupported, merge duplicates (spec 10.5)."""

from rapidfuzz import fuzz

from app.ai.domain.enums import ItemType
from app.ai.domain.models import MeetingItem
from app.ai.domain.names import norm_name

DUPLICATE = 90
MIN_CONFIDENCE = 0.6
REQUIRED_FLAGS: dict[ItemType, list[tuple[str, str]]] = {
    ItemType.DECISION: [("owner", "missing_owner")],
    ItemType.ACTION_ITEM: [("owner", "missing_owner"), ("due_date", "missing_due_date")],
    ItemType.REQUEST: [("requester", "missing_requester")],
}


def _owner_key(item: MeetingItem) -> str | None:
    return norm_name(item.owner) if item.owner else None


def _is_duplicate(a: MeetingItem, b: MeetingItem) -> bool:
    if a.type != b.type:
        return False
    if a.type == ItemType.ACTION_ITEM and _owner_key(a) != _owner_key(b):
        return False
    return fuzz.token_sort_ratio(a.content.casefold(), b.content.casefold()) >= DUPLICATE


def _merge(a: MeetingItem, b: MeetingItem) -> MeetingItem:
    keep, other = (b, a) if b.confidence > a.confidence else (a, b)
    seen = {e.utterance_id for e in keep.evidence}
    evidence = list(keep.evidence)
    for e in other.evidence:
        if e.utterance_id not in seen:
            seen.add(e.utterance_id)
            evidence.append(e)
    flags = list(dict.fromkeys([*keep.flags, *other.flags]))
    return keep.model_copy(update={"evidence": evidence, "flags": flags})


def _merge_duplicates(items: list[MeetingItem]) -> list[MeetingItem]:
    merged: list[MeetingItem] = []
    for item in items:
        for i, existing in enumerate(merged):
            if _is_duplicate(existing, item):
                merged[i] = _merge(existing, item)
                break
        else:
            merged.append(item)
    return merged


def _with_flags(item: MeetingItem) -> MeetingItem:
    flags = list(item.flags)
    wanted = [flag for attr, flag in REQUIRED_FLAGS.get(item.type, []) if not getattr(item, attr)]
    if item.confidence < MIN_CONFIDENCE:
        wanted.append("low_confidence")
    flags.extend(f for f in wanted if f not in flags)
    return item.model_copy(update={"flags": flags})


def validate_items(items: list[MeetingItem]) -> list[MeetingItem]:
    kept = [i for i in items if i.evidence]
    flagged = [_with_flags(i) for i in _merge_duplicates(kept)]
    return sorted(flagged, key=lambda i: (not i.flags, i.evidence[0].ts))
