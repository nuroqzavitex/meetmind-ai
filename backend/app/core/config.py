"""Service settings, loaded from the environment / .env."""

from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.ai.config import AISettings

JOB_TIMEOUT_SECONDS = 900
STALE_JOB_SECONDS = JOB_TIMEOUT_SECONDS + 120


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/meeting"
    redis_url: str = "redis://localhost:6379"
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    clerk_authorized_parties: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    llm_provider: Literal["anthropic", "openai", "fake"] = "anthropic"
    fake_llm_dir: str = "../tests/fixtures/llm/payment_v2"
    llm_model_default: str = "claude-sonnet-5-5"
    llm_model_arbitrate: str = "claude-opus-5-5"
    embedding_provider: Literal["local", "hash"] = "local"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    prompt_version: str = "v1"
    max_upload_bytes: int = 5_000_000
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

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
