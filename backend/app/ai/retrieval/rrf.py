def rrf_fuse(rankings: list[list[str]], *, k: int = 60, limit: int = 12) -> list[str]:
    """Reciprocal rank fusion: score(id) = sum 1/(k + rank), rank from 1."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    # dict preserves first-appearance order; sorted is stable, so ties keep it
    return sorted(scores, key=lambda key: -scores[key])[:limit]
