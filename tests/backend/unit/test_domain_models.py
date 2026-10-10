import pytest
from pydantic import ValidationError

from app.ai.domain.enums import Act, ItemStatus, ItemType, ReviewState
from app.ai.domain.models import DialogueAct, MeetingItem


def test_dialogue_act_confidence_bounds():
    with pytest.raises(ValidationError):
        DialogueAct(id="a1", utterance_id="u0001", seq=1, speaker="Lan", start=0,
                    act=Act.DECIDE, quote="x", confidence=1.2)


def test_meeting_item_defaults():
    it = MeetingItem(id="i1", meeting_id="m1", type=ItemType.DECISION, content="c", evidence=[])
    assert it.status == ItemStatus.FINAL and it.review_state == ReviewState.PENDING and it.flags == []
