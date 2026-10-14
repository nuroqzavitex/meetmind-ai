"""Text embedders: deterministic hash (tests), local sentence-transformers, and Gemini API."""

import asyncio
import hashlib
import math
import threading
import unicodedata
from typing import Any, Protocol

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.ai.errors import EmbeddingError


class Embedder(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def _tokens(text: str) -> list[str]:
    words = unicodedata.normalize("NFC", text).casefold().split()
    out: list[str] = []
    for word in words:
        out.append(f"w:{word}")
        padded = f"^{word}$"
        out.extend(f"t:{padded[i : i + 3]}" for i in range(len(padded) - 2))
    return out


class HashEmbedder:
    """Deterministic feature-hashing embedder: no model download, stable across runs."""

    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            sign = 1.0 if (value >> 63) & 1 else -1.0
            vec[value % self.dim] += sign
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            return vec
        return [x / norm for x in vec]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]


class LocalEmbedder:
    """sentence-transformers model, imported and loaded lazily on first use."""

    def __init__(self, model: str, dim: int) -> None:
        self.model_name = model
        self.dim = dim
        self._model: Any = None
        self._lock = threading.Lock()

    def _load(self) -> Any:
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as e:
                    raise EmbeddingError(
                        "Thiếu gói sentence-transformers (cài extra 'embeddings')"
                    ) from e
                self._model = SentenceTransformer(self.model_name)
            return self._model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(texts, normalize_embeddings=True)
        return [[float(x) for x in v] for v in vectors]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            vectors = await asyncio.to_thread(self._encode, texts)
        except EmbeddingError:
            raise
        except Exception as e:
            raise EmbeddingError(f"Không tạo được embedding: {e}") from e
        for v in vectors:
            if len(v) != self.dim:
                raise EmbeddingError(f"Embedding có {len(v)} chiều, cần {self.dim}")
        return vectors


class GeminiEmbedder:
    """Gemini embedding API; vectors are requested at `dim` and L2-normalised.

    With `client=None` (no API key) it fails only when used, so the API and worker still start.
    """

    def __init__(self, model: str, dim: int, client: Any = None) -> None:
        self.model_name = model
        self.dim = dim
        self._client = client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._client is None:
            raise EmbeddingError("GEMINI_API_KEY chưa được cấu hình")
        try:
            response = await self._client.aio.models.embed_content(
                model=self.model_name,
                contents=texts,
                config=genai_types.EmbedContentConfig(output_dimensionality=self.dim),
            )
        except genai_errors.APIError as e:
            raise EmbeddingError(f"Lỗi Gemini API khi tạo embedding: {e}") from e
        embeddings = response.embeddings or []
        if len(embeddings) != len(texts):
            raise EmbeddingError(f"Gemini trả {len(embeddings)} embedding cho {len(texts)} đoạn")
        vectors = [_normalize([float(x) for x in (e.values or [])]) for e in embeddings]
        for v in vectors:
            if len(v) != self.dim:
                raise EmbeddingError(f"Embedding có {len(v)} chiều, cần {self.dim}")
        return vectors


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return vec if norm == 0 else [x / norm for x in vec]


def make_embedder(provider: str, model: str, dim: int, api_key: str | None = None) -> Embedder:
    if provider == "hash":
        return HashEmbedder(dim)
    if provider == "local":
        return LocalEmbedder(model, dim)
    if provider == "gemini":
        return GeminiEmbedder(model, dim, genai.Client(api_key=api_key) if api_key else None)
    raise EmbeddingError(f"Embedding provider không hợp lệ: {provider}")
