"""Text embedders: a deterministic hash embedder (tests) and a local sentence-transformers one."""

import asyncio
import hashlib
import math
import threading
import unicodedata
from typing import Any, Protocol

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


def make_embedder(provider: str, model: str, dim: int) -> Embedder:
    if provider == "hash":
        return HashEmbedder(dim)
    if provider == "local":
        return LocalEmbedder(model, dim)
    raise EmbeddingError(f"Embedding provider không hợp lệ: {provider}")
