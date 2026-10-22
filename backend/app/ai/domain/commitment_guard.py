"""Code-side check that a decision or task was actually committed to, not just floated.

The LLM labels "hay là ai đó viết lại tài liệu nhỉ" or "dạ, em chờ tin anh" as task assignments
often enough that an extracted item cannot be trusted to be a commitment. This guard runs after
build_items and never drops an item: it flags the ones that read as a suggestion, a condition,
a refusal, a wait or a decision whose label lost its "không", and records in `item.hold` the
sentence and the exact phrase that triggered it, so the reviewer sees why and confirms the item
instead of it being published as official. Matching keeps diacritics: "chờ" (wait) and "cho"
(give) differ only by them.
"""

import re
import unicodedata

from app.ai.domain.enums import ItemType
from app.ai.domain.models import Evidence, Hold, HoldReason, MeetingItem, Utterance
from app.ai.domain.names import norm_name
from app.ai.domain.timefmt import fmt_ts

NEEDS_CONFIRMATION = "needs_confirmation"
TENTATIVE = "tentative"
CONDITIONAL = "conditional"
DECLINED = "declined"
WAITING = "waiting"
NEGATION = "negation"
# Everything this guard may add; confirming an item removes them all.
GUARD_FLAGS = (NEEDS_CONFIRMATION, TENTATIVE, CONDITIONAL, DECLINED, WAITING, NEGATION)
# The hold shown to the reviewer when several apply: the strongest evidence first.
_PRIORITY: list[HoldReason] = [
    "declined", "conditional", "negation", "waiting", "tentative", "no_owner",
]  # fmt: skip

_TENTATIVE = [
    "hay là", "hay mình", "hay ai", "ai đó", "ai rảnh", "có lẽ", "chắc là", "nên chăng",
    "thử xem", "xem sao", "tính sau", "để sau", "nếu được", "nếu kịp", "may ra", "biết đâu",
    "có khi", "để xem", "tạm chốt", "chốt sơ bộ", "chưa chắc", "chưa quyết",
]  # fmt: skip
_CONDITIONAL = ["chỉ khi", "trong trường hợp", "với điều kiện", "miễn là"]
_DECLINE = [
    "không nhận", "không kịp", "không làm được", "không làm nổi", "không kham", "kín lịch",
    "chưa nhận được", "nhờ người khác", "để người khác", "không rảnh",
]  # fmt: skip
_B, _E = r"(?<!\w)", r"(?!\w)"  # word edges that also work next to Vietnamese letters
_IF_THEN = re.compile(rf"{_B}nếu{_E}.+?{_B}thì{_E}", re.IGNORECASE | re.DOTALL)
_WAIT = re.compile(
    rf"{_B}(chờ|đợi){_E}(\s+\S+){{0,3}}?\s+(tin|báo|phản hồi|ý kiến|trả lời){_E}", re.IGNORECASE
)
# "chốt không mời Bách": the decision itself is a "no".
_NEGATED_DECIDE = re.compile(
    rf"{_B}(chốt|quyết định|thống nhất){_E}\s+(là\s+)?"
    rf"(không|chưa|bỏ|thôi|hủy|huỷ|dừng|ngừng){_E}",
    re.IGNORECASE,
)
_NEGATIVE_LABEL = ["không", "chưa", "bỏ", "thôi", "hủy", "huỷ", "dừng", "ngừng", "giữ nguyên",
                   "hoãn"]  # fmt: skip
# Owners that name nobody in particular.
_NOBODY = {"ai đó", "ai do", "mọi người", "moi nguoi", "cả team", "ca team", "team", "cả nhóm",
           "ca nhom", "nhóm", "nhom"}  # fmt: skip
# build_items turns "chưa chắc, để anh xin ý kiến X" into "Xin ý kiến: …" for the speaker: the doubt
# is about the decision, while asking is a real commitment. It also does so for a bare "để sau
# tính", which asks nobody, so the exemption needs the words of asking in what was said.
ASK_PERMISSION = "xin ý kiến"
_ASKING = ["ý kiến", "hỏi", "xin phép", "báo lại"]
DECLINE_WINDOW = 3  # utterances after the assignment in which the assignee may refuse


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _phrase_re(phrases: list[str]) -> re.Pattern[str]:
    alts = "|".join(r"\s+".join(map(re.escape, p.split())) for p in phrases)
    return re.compile(rf"{_B}({alts}){_E}", re.IGNORECASE)


_TENTATIVE_RE = _phrase_re(_TENTATIVE)
_CONDITIONAL_RE = _phrase_re(_CONDITIONAL)
_DECLINE_RE = _phrase_re(_DECLINE)
_ASKING_RE = _phrase_re(_ASKING)
_NEGATIVE_LABEL_RE = _phrase_re(_NEGATIVE_LABEL)


def _find(pattern: re.Pattern[str], text: str) -> str | None:
    """The matched words exactly as written in `text` (NFC), or None."""
    m = pattern.search(_nfc(text))
    return m.group(0) if m else None


def tentative_phrase(text: str) -> str | None:
    return _find(_TENTATIVE_RE, text)


def conditional_phrase(text: str) -> str | None:
    return _find(_IF_THEN, text) or _find(_CONDITIONAL_RE, text)


def declining_phrase(text: str) -> str | None:
    return _find(_DECLINE_RE, text)


def waiting_phrase(text: str) -> str | None:
    return _find(_WAIT, text)


def negated_decide_phrase(text: str) -> str | None:
    return _find(_NEGATED_DECIDE, text)


def is_tentative(text: str) -> bool:
    return tentative_phrase(text) is not None


def is_conditional(text: str) -> bool:
    return conditional_phrase(text) is not None


def is_declining(text: str) -> bool:
    return declining_phrase(text) is not None


def is_waiting(text: str) -> bool:
    return waiting_phrase(text) is not None


def _norm(s: str) -> str:
    return " ".join(_nfc(s).casefold().split())


def _add(flags: list[str], *new: str) -> list[str]:
    return list(dict.fromkeys([*flags, *new]))


def _hold(reason: HoldReason, said: str, phrase: str | None, u: Utterance | None,
          ev: Evidence | None = None) -> Hold:
    return Hold(
        reason=reason, quote=_nfc(said), phrase=phrase,
        speaker=u.speaker if u else (ev.speaker if ev else None),
        ts=fmt_ts(u.start) if u else (ev.ts if ev else None),
    )


def _said(e: Evidence, by_id: dict[str, Utterance]) -> tuple[str, Utterance | None]:
    """The whole sentence behind a piece of evidence (the LLM may quote only part of it)."""
    u = by_id.get(e.utterance_id)
    return (u.text if u else e.quote), u


def _decline(item: MeetingItem, owner: str, by_id: dict[str, Utterance],
             utts: list[Utterance]) -> tuple[Utterance, str] | None:
    seqs = [by_id[e.utterance_id].seq for e in item.evidence if e.utterance_id in by_id]
    if not seqs:
        return None
    last = max(seqs)
    who = norm_name(owner)
    for u in utts:
        if last < u.seq <= last + DECLINE_WINDOW and norm_name(u.speaker) == who:
            phrase = declining_phrase(u.text)
            if phrase:
                return u, phrase
    return None


def _apply(item: MeetingItem, holds: list[Hold], *, flags: list[str],
           **update: object) -> MeetingItem:
    if not holds:
        return item.model_copy(update={"flags": flags, **update})
    holds.sort(key=lambda h: _PRIORITY.index(h.reason))
    reasons = [h.reason for h in holds if h.reason != "no_owner"]
    return item.model_copy(update={
        "flags": _add(flags, NEEDS_CONFIRMATION, *reasons), "hold": holds[0], **update,
    })


def _guard_task(item: MeetingItem, by_id: dict[str, Utterance],
                utts: list[Utterance]) -> MeetingItem:
    owner = item.owner
    if owner is not None and _norm(owner) in _NOBODY:
        owner = None
    first = item.evidence[0]
    first_said, first_u = _said(first, by_id)
    holds: list[Hold] = []
    evidence = list(item.evidence)

    # A suggestion stops being one once its owner says something firm about it.
    taken = owner is not None and any(
        norm_name(e.speaker) == norm_name(owner) and not is_tentative(e.quote)
        for e in item.evidence
    )
    asking = _norm(item.content).startswith(ASK_PERMISSION) and any(
        _find(_ASKING_RE, e.quote) for e in item.evidence
    )
    phrase = tentative_phrase(first.quote)
    if phrase and not taken and not asking:
        holds.append(_hold("tentative", first_said, phrase, first_u, first))

    condition = item.condition
    for e in item.evidence:
        said, u = _said(e, by_id)
        phrase = conditional_phrase(said)
        if phrase:
            holds.append(_hold("conditional", said, phrase, u, e))
            condition = condition or said
            break
    else:
        if condition:
            holds.append(_hold("conditional", first_said, None, first_u, first))

    if all(is_waiting(e.quote) for e in item.evidence):
        holds.append(_hold("waiting", first_said, waiting_phrase(first.quote), first_u, first))

    if owner is not None:
        found = _decline(item, owner, by_id, utts)
        if found:
            u, phrase = found
            holds.append(_hold("declined", u.text, phrase, u))
            evidence.append(Evidence(  # the refusal is part of why the task is not official
                utterance_id=u.id, speaker=u.speaker, ts=fmt_ts(u.start), quote=u.text))
    if owner is None:
        holds.append(_hold("no_owner", first_said, None, first_u, first))
    return _apply(item, holds, flags=item.flags, owner=owner, condition=condition,
                  evidence=evidence)


def _guard_decision(item: MeetingItem, by_id: dict[str, Utterance]) -> MeetingItem:
    first = item.evidence[0]
    said, u = _said(first, by_id)
    holds: list[Hold] = []
    flags = item.flags
    phrase = tentative_phrase(first.quote)
    if phrase:
        holds.append(_hold("tentative", said, phrase, u, first))
    label = item.content.rsplit("→", 1)[-1]
    phrase = negated_decide_phrase(said)
    if phrase and not _find(_NEGATIVE_LABEL_RE, label):
        holds.append(_hold("negation", said, phrase, u, first))
    if item.condition or is_conditional(first.quote):
        flags = _add(flags, CONDITIONAL)  # still decided, but only under that condition
    return _apply(item, holds, flags=flags)


def guard_items(items: list[MeetingItem], utterances: list[Utterance]) -> list[MeetingItem]:
    by_id = {u.id: u for u in utterances}
    out = []
    for item in items:
        if not item.evidence:
            out.append(item)
        elif item.type == ItemType.ACTION_ITEM:
            out.append(_guard_task(item, by_id, utterances))
        elif item.type == ItemType.DECISION:
            out.append(_guard_decision(item, by_id))
        else:
            out.append(item)
    return out


def release(item: MeetingItem) -> MeetingItem:
    """A reviewer confirmed the item: it becomes official, without the guard's hold and flags."""
    flags = [f for f in item.flags if f not in GUARD_FLAGS]
    return item.model_copy(update={"hold": None, "flags": flags})
