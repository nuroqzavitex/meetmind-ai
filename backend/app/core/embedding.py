"""Pick the embedder for the API and worker from settings."""

from app.ai.retrieval.embedder import Embedder, make_embedder
from app.core.config import Settings


def build_embedder(settings: Settings) -> Embedder:
    key = settings.gemini_api_key
    return make_embedder(
        settings.embedding_provider,
        settings.embedding_model,
        settings.embedding_dim,
        api_key=key.get_secret_value() if key else None,
    )
