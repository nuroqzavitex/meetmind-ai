"""Service settings, loaded from the environment / .env."""

from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.ai.config import AISettings

JOB_TIMEOUT_SECONDS = 900
STALE_JOB_SECONDS = JOB_TIMEOUT_SECONDS + 120

# libpq-only query params that asyncpg.connect() rejects as unknown keyword arguments.
_LIBPQ_ONLY_PARAMS = {"channel_binding"}


def normalize_database_url(url: str) -> str:
    """Accept hosted-Postgres URLs (Neon, Supabase, Render) as pasted.

    They use the plain `postgres(ql)://` scheme and libpq's `sslmode`; SQLAlchemy's asyncpg
    dialect needs `postgresql+asyncpg://` and asyncpg's `ssl`.
    """
    scheme, sep, rest = url.partition("://")
    if not sep or scheme not in ("postgres", "postgresql"):
        return url
    base, _, query = rest.partition("?")
    params = []
    for pair in filter(None, query.split("&")):
        key, _, value = pair.partition("=")
        if key in _LIBPQ_ONLY_PARAMS:
            continue
        params.append(f"ssl={value}" if key == "sslmode" else pair)
    return f"postgresql+asyncpg://{base}" + (f"?{'&'.join(params)}" if params else "")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/meeting"
    redis_url: str = "redis://localhost:6379"
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    clerk_authorized_parties: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    # Clerk Backend API key (sk_...): adds members when an admin approves a join request.
    clerk_secret_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    # Ollama Cloud through its OpenAI-compatible API (models like gemma4:31b).
    ollama_api_key: SecretStr | None = None
    ollama_base_url: str = "https://ollama.com/v1"
    llm_provider: Literal["anthropic", "openai", "ollama", "fake"] = "anthropic"
    fake_llm_dir: str = "../tests/fixtures/llm/payment_v2"
    llm_model_default: str = "claude-sonnet-5-5"
    llm_model_arbitrate: str = "claude-opus-5-5"
    embedding_provider: Literal["local", "hash", "gemini"] = "local"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    prompt_version: str = "v1"
    max_upload_bytes: int = 5_000_000
    # Audio uploads (diarized transcription). OpenAI's transcription endpoint caps files at 25 MB.
    max_audio_bytes: int = 25_000_000
    stt_model: str = "gpt-4o-transcribe-diarize"
    # Seconds between Arq queue polls. Raise it on metered Redis (Upstash free: 500k commands/month).
    worker_poll_delay: float = 0.5
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    # Public frontend URL, used for links in Discord messages.
    frontend_url: str = "http://localhost:3000"
    # Shared secret for POST /internal/digest (the scheduled daily reminder); empty disables it.
    cron_secret: SecretStr | None = None
    # Discord Q&A bot (slash commands over the HTTP Interactions Endpoint).
    discord_app_id: str = ""
    discord_public_key: str = ""
    discord_bot_token: SecretStr | None = None  # only for scripts/register_discord_commands.py

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("clerk_authorized_parties", "cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    def ai_settings(self) -> AISettings:
        return AISettings(
            prompt_version=self.prompt_version,
            models={"default": self.llm_model_default, "arbitrate": self.llm_model_arbitrate},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
