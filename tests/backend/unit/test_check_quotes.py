from app.ai.agents.check_quotes import check_quotes
from app.ai.domain.enums import Act
from app.ai.domain.models import DialogueAct, Utterance

UTTS = {
    "u0001": Utterance(id="u0001", seq=1, speaker="Minh", start=20.0, text="Em đề xuất dùng MongoDB cho nhanh, schema linh hoạt."),
}


def act_q(uid: str, quote: str) -> DialogueAct:
    return DialogueAct(id="a", utterance_id=uid, seq=1, speaker="Minh", start=20.0, act=Act.PROPOSE, quote=quote)


def test_check_quotes():
    ok, bad_ratio = check_quotes([act_q("u0001", "dùng MongoDB cho nhanh"), act_q("u0001", "dùng Cassandra")], UTTS)
    assert len(ok) == 1 and bad_ratio == 0.5


def test_check_quotes_casefold():
    ok, _ = check_quotes([act_q("u0001", "DÙNG MONGODB")], UTTS)
    assert len(ok) == 1


def test_check_quotes_unknown_utterance_is_invalid():
    ok, ratio = check_quotes([act_q("u9999", "dùng MongoDB")], UTTS)
    assert ok == [] and ratio == 1.0


def test_check_quotes_empty():
    assert check_quotes([], UTTS) == ([], 0.0)
