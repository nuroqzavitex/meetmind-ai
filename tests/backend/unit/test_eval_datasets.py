from pathlib import Path

import pytest
from evals.metrics.matching import Golden, contains_keyword, decision_label

from app.ai.domain.enums import ItemType

from app.ai.parsing import parse_transcript

EVALS = Path(__file__).resolve().parents[3] / "evals"
GOLDEN_FILES = sorted((EVALS / "golden").glob("*.json"))


def _load(path: Path) -> Golden:
    return Golden.model_validate_json(path.read_text(encoding="utf-8"))


def test_golden_files_exist() -> None:
    assert GOLDEN_FILES


@pytest.mark.parametrize("path", GOLDEN_FILES, ids=lambda p: p.stem)
def test_golden_valid_and_transcript_parses(path: Path) -> None:
    g = _load(path)
    tpath = EVALS / g.transcript
    assert tpath.is_file(), tpath
    utts = parse_transcript(tpath.name, tpath.read_bytes())
    assert len(utts) >= 8
    starts = [u.start for u in utts]
    assert starts == sorted(starts)
    assert g.context.meeting_id == path.stem
    assert g.items and g.topics
    expected_dir = "synthetic" if g.kind == "trap" else "transcripts"
    assert g.transcript == f"datasets/{expected_dir}/{path.stem}.txt"


MIN_KEYWORD = 4
MIN_OPTION_KEYWORD = 3  # option names are often short acronyms (SES, ZNS)


def _check_keywords(stem: str, kws: list[str], min_len: int) -> None:
    assert kws, stem
    for kw in kws:
        assert len(kw) >= min_len, (stem, kw)
        assert kw.isascii() and kw == kw.lower(), (stem, kw)


@pytest.mark.parametrize("path", GOLDEN_FILES, ids=lambda p: p.stem)
def test_match_keywords_specific(path: Path) -> None:
    g = _load(path)
    for t in g.topics:
        _check_keywords(path.stem, t.match, MIN_KEYWORD)
    for it in g.items:
        is_decision = it.type == ItemType.DECISION
        _check_keywords(path.stem, it.match, MIN_OPTION_KEYWORD if is_decision else MIN_KEYWORD)
        text = decision_label(it.content) if is_decision else it.content
        assert contains_keyword(text, it.match), (path.stem, it.content)


@pytest.mark.parametrize("path", GOLDEN_FILES, ids=lambda p: p.stem)
def test_topics_with_final_option_have_final_match(path: Path) -> None:
    for t in _load(path).topics:
        if t.final_option is None:
            assert t.final_match == [], (path.stem, t.question)
            continue
        _check_keywords(path.stem, t.final_match, MIN_OPTION_KEYWORD)
        assert contains_keyword(t.final_option, t.final_match), (path.stem, t.question)


@pytest.mark.parametrize("path", GOLDEN_FILES, ids=lambda p: p.stem)
def test_keywords_not_shared_between_items_of_same_type(path: Path) -> None:
    g = _load(path)
    seen: dict[tuple[ItemType, str], int] = {}
    for n, it in enumerate(g.items):
        for kw in it.match:
            assert seen.setdefault((it.type, kw), n) == n, (path.stem, kw)


def test_dataset_size() -> None:
    kinds = [_load(p).kind for p in GOLDEN_FILES]
    assert kinds.count("trap") >= 10
    assert kinds.count("realistic") >= 4


REQUIRED_TRAPS = {
    "a_to_b", "b_back_to_a", "decide_a_then_b", "reject_decided", "ambiguous_decide",
    "conditional_decide", "wait_for_boss", "joke_hypothetical", "implicit_assignment",
    "relative_deadlines",
}


def test_required_trap_scenarios_present() -> None:
    names = {p.stem for p in GOLDEN_FILES if _load(p).kind == "trap"}
    assert REQUIRED_TRAPS <= names
