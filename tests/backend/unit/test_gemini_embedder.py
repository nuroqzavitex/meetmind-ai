import math
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors

from app.ai.errors import EmbeddingError
from app.ai.retrieval.embedder import GeminiEmbedder, make_embedder


class StubGenAI:
    def __init__(self, vectors: list[list[float]] | None = None, error: Exception | None = None):
        self.calls: list[dict[str, Any]] = []

        async def embed_content(**kwargs: Any) -> Any:
            self.calls.append(kwargs)
            if error is not None:
                raise error
            assert vectors is not None
            return SimpleNamespace(embeddings=[SimpleNamespace(values=v) for v in vectors])

        self.aio = SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))


async def test_gemini_embedder_requests_dim_and_normalizes() -> None:
    stub = StubGenAI([[3.0, 4.0, 0.0], [0.0, 0.0, 2.0]])
    emb = GeminiEmbedder("gemini-embedding-001", 3, client=stub)
    out = await emb.embed(["một", "hai"])
    assert out == [[0.6, 0.8, 0.0], [0.0, 0.0, 1.0]]
    call = stub.calls[0]
    assert call["model"] == "gemini-embedding-001"
    assert call["contents"] == ["một", "hai"]
    assert call["config"].output_dimensionality == 3


async def test_gemini_embedder_rejects_wrong_dimension() -> None:
    emb = GeminiEmbedder("m", 4, client=StubGenAI([[1.0, 0.0]]))
    with pytest.raises(EmbeddingError, match="2 chiều"):
        await emb.embed(["x"])


async def test_gemini_embedder_rejects_count_mismatch() -> None:
    emb = GeminiEmbedder("m", 2, client=StubGenAI([[1.0, 0.0]]))
    with pytest.raises(EmbeddingError):
        await emb.embed(["a", "b"])


async def test_gemini_api_error_becomes_embedding_error() -> None:
    err = errors.APIError(500, {"error": {"message": "boom", "status": "INTERNAL"}})
    emb = GeminiEmbedder("m", 2, client=StubGenAI(error=err))
    with pytest.raises(EmbeddingError, match="Gemini"):
        await emb.embed(["x"])


async def test_gemini_without_key_fails_only_when_used() -> None:
    emb = make_embedder("gemini", "gemini-embedding-001", 1024, api_key=None)
    assert emb.dim == 1024
    with pytest.raises(EmbeddingError, match="GEMINI_API_KEY"):
        await emb.embed(["x"])


async def test_gemini_empty_input_makes_no_call() -> None:
    stub = StubGenAI([])
    assert await GeminiEmbedder("m", 2, client=stub).embed([]) == []
    assert stub.calls == []


def test_make_embedder_gemini_with_key() -> None:
    emb = make_embedder("gemini", "gemini-embedding-001", 1024, api_key="k")
    assert isinstance(emb, GeminiEmbedder)
    assert math.isclose(emb.dim, 1024)
