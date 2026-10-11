import builtins
import math
from typing import Any

import pytest

from app.ai.errors import EmbeddingError
from app.ai.retrieval.embedder import HashEmbedder, LocalEmbedder, make_embedder


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


async def test_hash_vectors_are_unit_and_sized() -> None:
    vecs = await HashEmbedder(64).embed(["chốt Postgres cho thanh toán"])
    assert len(vecs[0]) == 64
    assert math.isclose(math.sqrt(sum(x * x for x in vecs[0])), 1.0, rel_tol=1e-9)


async def test_hash_is_deterministic() -> None:
    e = HashEmbedder(64)
    a, b = await e.embed(["dùng Postgres", "dùng Postgres"])
    assert a == b


async def test_hash_shared_words_score_higher() -> None:
    e = HashEmbedder(1024)
    q, near, far = await e.embed(
        ["chốt Postgres cho thanh toán", "dùng Postgres", "báo cáo giao dịch lỗi"]
    )
    assert _cos(q, near) > _cos(q, far)


async def test_hash_empty_text_is_zero_vector() -> None:
    (v,) = await HashEmbedder(32).embed([""])
    assert v == [0.0] * 32


def test_make_embedder() -> None:
    e = make_embedder("hash", "x", 16)
    assert isinstance(e, HashEmbedder) and e.dim == 16
    assert isinstance(make_embedder("local", "m", 16), LocalEmbedder)


async def test_local_embedder_missing_package_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("sentence_transformers"):
            raise ImportError("no module")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(EmbeddingError):
        await LocalEmbedder("m", 8).embed(["x"])


def test_local_embedder_loads_model_once_under_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    import threading
    import time
    import types

    loads: list[str] = []

    class FakeST:
        def __init__(self, name: str) -> None:
            loads.append(name)
            time.sleep(0.05)

    monkeypatch.setitem(
        sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=FakeST)
    )
    emb = LocalEmbedder("m", 4)
    threads = [threading.Thread(target=emb._load) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert loads == ["m"]
