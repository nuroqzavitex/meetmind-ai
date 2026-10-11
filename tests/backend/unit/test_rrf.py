from app.ai.retrieval.rrf import rrf_fuse


def test_fuse_orders_by_score() -> None:
    assert rrf_fuse([["a", "b", "c"], ["c", "a"]]) == ["a", "c", "b"]


def test_limit_and_empty() -> None:
    assert rrf_fuse([["a", "b", "c"]], limit=2) == ["a", "b"]
    assert rrf_fuse([]) == []
    assert rrf_fuse([[], []]) == []


def test_single_ranking_only_id_appears() -> None:
    assert "z" in rrf_fuse([["a"], ["z"]])


def test_ties_by_first_appearance() -> None:
    assert rrf_fuse([["a"], ["b"]]) == ["a", "b"]
