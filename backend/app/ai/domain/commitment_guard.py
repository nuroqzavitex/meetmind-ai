"""Code-side check that a decision or task was actually committed to, not just floated.

The LLM labels "hay là ai đó viết lại tài liệu nhỉ" or "dạ, em chờ tin anh" as task assignments
often enough that an extracted item cannot be trusted to be a commitment. This guard runs after
build_items and never drops an item: it only flags the ones that read as a suggestion, a
condition, a refusal or a wait, so the reviewer confirms them instead of publishing them as
official. Matching keeps diacritics: "chờ" (wait) and "cho" (give) differ only by them.
"""

import re
import unicodedata

from app.ai.domain.enums import ItemType
from app.ai.domain.models import MeetingItem, Utterance
from app.ai.domain.names import norm_name

NEEDS_CONFIRMATION = "needs_confirmation"
TENTATIVE = "tentative"
CONDITIONAL = "conditional"
DECLINED = "declined"
WAITING = "waiting"

_TENTATIVE = [
    "hay là", "hay mình", "hay ai", "ai đó", "ai rảnh", "có lẽ", "chắc là", "nên chăng",
    "thử xem", "xem sao", "tính sau", "để sau", "nếu được", "nếu kịp", "may ra", "biết đâu",
    "có khi", "để xem", "tạm chốt", "chốt sơ bộ", "chưa chắc",
]  # fmt: skip
_CONDITIONAL = ["chỉ khi", "trong trường hợp", "với điều kiện", "miễn là"]
_DECLINE = [
    "không nhận", "không kịp", "không làm được", "không làm nổi", "không kham", "kín lịch",
    "chưa nhận được", "nhờ người khác", "để người khác", "không rảnh",
]  # fmt: skip
_IF_THEN = re.compile(r"\bnếu\b.+\bthì\b")
_WAIT = re.compile(r"\b(chờ|đợi)\b(\s+\S+){0,3}?\s+(tin|báo|phản hồi|ý kiến|trả lời)\b")
# Owners that name nobody in particular.
_NOBODY = {"ai đó", "ai do", "mọi người", "moi nguoi", "cả team", "ca team", "team", "cả nhóm",
           "ca nhom", "nhóm", "nhom"}  # fmt: skip
# build_items turns "chưa chắc, để anh xin ý kiến X" into "Xin ý kiến: …" for the speaker: the doubt
# is about the decision, while asking is a real commitment.
ASK_PERMISSION = "xin ý kiến"
DECLINE_WINDOW = 3  # utterances after the assignment in which the assignee may refuse


def _text(s: str) -> str:
    return " ".join(unicodedata.normalize("NFC", s).casefold().split())


def _has_phrase(text: str, phrases: list[str]) -> bool:
    t = " " + " ".join(re.sub(r"[^\w\s]", " ", _text(text)).split()) + " "
    return any(f" {p} " in t for p in phrases)


def is_tentative(text: str) -> bool:
    return _has_phrase(text, _TENTATIVE)


def is_conditional(text: str) -> bool:
    return bool(_IF_THEN.search(_text(text))) or _has_phrase(text, _CONDITIONAL)


def is_declining(text: str) -> bool:
    return _has_phrase(text, _DECLINE)


def is_waiting(text: str) -> bool:
    return bool(_WAIT.search(_text(text)))


def _add(flags: list[str], *new: str) -> list[str]:
    return list(dict.fromkeys([*flags, *new]))


def _declined(item: MeetingItem, owner: str, by_id: dict[str, Utterance],
              utts: list[Utterance]) -> bool:
    seqs = [by_id[e.utterance_id].seq for e in item.evidence if e.utterance_id in by_id]
    if not seqs:
        return False
    last = max(seqs)
    who = norm_name(owner)
    return any(
        norm_name(u.speaker) == who and is_declining(u.text)
        for u in utts
        if last < u.seq <= last + DECLINE_WINDOW
    )


def _guard_task(item: MeetingItem, by_id: dict[str, Utterance],
                utts: list[Utterance]) -> MeetingItem:
    owner = item.owner
    if owner is not None and _text(owner) in _NOBODY:
        owner = None
    quotes = [e.quote for e in item.evidence]
    reasons: list[str] = []
    first = item.evidence[0]
    # A suggestion stops being one once its owner says something firm about it.
    taken = owner is not None and any(
        norm_name(e.speaker) == norm_name(owner) and not is_tentative(e.quote)
        for e in item.evidence
    )
    asking = _text(item.content).startswith(ASK_PERMISSION)
    if is_tentative(first.quote) and not taken and not asking:
        reasons.append(TENTATIVE)
    condition = item.condition
    if condition or any(is_conditional(q) for q in quotes):
        reasons.append(CONDITIONAL)
        condition = condition or next(q for q in quotes if is_conditional(q))
    if all(is_waiting(q) for q in quotes):
        reasons.append(WAITING)
    if owner is not None and _declined(item, owner, by_id, utts):
        reasons.append(DECLINED)
    if owner is None or reasons:
        flags = _add(item.flags, NEEDS_CONFIRMATION, *reasons)
    else:
        flags = item.flags
    return item.model_copy(update={"owner": owner, "condition": condition, "flags": flags})


def _guard_decision(item: MeetingItem) -> MeetingItem:
    flags = item.flags
    if is_tentative(item.evidence[0].quote):
        flags = _add(flags, NEEDS_CONFIRMATION, TENTATIVE)
    if item.condition or is_conditional(item.evidence[0].quote):
        flags = _add(flags, CONDITIONAL)  # still decided, but only under that condition
    return item.model_copy(update={"flags": flags})


def guard_items(items: list[MeetingItem], utterances: list[Utterance]) -> list[MeetingItem]:
    by_id = {u.id: u for u in utterances}
    out = []
    for item in items:
        if not item.evidence:
            out.append(item)
        elif item.type == ItemType.ACTION_ITEM:
            out.append(_guard_task(item, by_id, utterances))
        elif item.type == ItemType.DECISION:
            out.append(_guard_decision(item))
        else:
            out.append(item)
    return out
