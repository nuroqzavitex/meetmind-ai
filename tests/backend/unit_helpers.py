from pathlib import Path

from app.ai.domain.models import Utterance

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "transcripts"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def utt(text: str, i: int = 0) -> Utterance:
    return Utterance(id=f"u{i:04d}", seq=i, speaker="Lan", start=float(i), text=text)
