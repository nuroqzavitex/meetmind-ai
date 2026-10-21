from pathlib import Path

from evals.runners.replay_guard import replay

from app.ai.domain.models import Evidence, MeetingItem
from app.ai.parsing import parse_transcript

EVALS = Path(__file__).resolve().parents[3] / "evals"


def _item(content: str, quote: str, owner: str, utt_id: str, speaker: str) -> dict[str, object]:
    return MeetingItem(
        id="i", meeting_id="wait_for_boss", type="action_item", content=content, owner=owner,
        evidence=[Evidence(utterance_id=utt_id, speaker=speaker, ts="00:00:00", quote=quote)],
    ).model_dump(mode="json")


def test_replay_flags_the_wait_and_changes_nothing_else() -> None:
    path = EVALS / "datasets" / "synthetic" / "wait_for_boss.txt"
    utts = {u.text: u for u in parse_transcript(path.name, path.read_bytes())}
    ask = utts["Để em xin ý kiến chị Thảo rồi báo lại cả nhóm."]
    wait = utts["Dạ, vậy em chờ tin từ Long."]
    report = {"meetings": {"wait_for_boss": {"items": [
        _item("Xin ý kiến chị Thảo về license Figma", ask.text, "Long", ask.id, ask.speaker),
        _item("Chờ tin từ Long", wait.text, "Nhi", wait.id, wait.speaker),
    ]}}}
    saved, guarded = replay(report)
    assert saved["official_precision"] == 0.5
    assert guarded["official_precision"] == 1.0
    for metric in ("precision", "recall", "final_decision_accuracy", "evidence_faithfulness"):
        assert saved[metric] == guarded[metric], metric
