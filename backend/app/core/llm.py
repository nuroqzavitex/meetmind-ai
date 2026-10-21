"""Pick the LLM client for the API and worker from settings."""

from pathlib import Path
from typing import Any

from app.ai.errors import LLMError
from app.ai.llm import LLMClient
from app.ai.llm.factory import make_llm, make_openai_llm
from app.ai.llm.fixture import FixtureLLM
from app.core.config import Settings


class UnconfiguredLLM:
    """Stands in when no API key is set; fails only when an LLM call is actually made."""

    def __init__(self, key_name: str = "ANTHROPIC_API_KEY") -> None:
        self._key_name = key_name

    async def structured(self, **_: Any) -> Any:
        raise LLMError(f"{self._key_name} chưa được cấu hình")


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "fake":
        return FixtureLLM(Path(settings.fake_llm_dir))
    if settings.llm_provider == "ollama":
        if settings.ollama_api_key is None:
            return UnconfiguredLLM("OLLAMA_API_KEY")
        return make_openai_llm(
            settings.ai_settings(),
            settings.ollama_api_key.get_secret_value(),
            base_url=settings.ollama_base_url,
        )
    if settings.llm_provider == "openai":
        if settings.openai_api_key is None:
            return UnconfiguredLLM("OPENAI_API_KEY")
        return make_openai_llm(settings.ai_settings(), settings.openai_api_key.get_secret_value())
    key = settings.anthropic_api_key
    if key is None:
        return UnconfiguredLLM()
    return make_llm(settings.ai_settings(), key.get_secret_value())
