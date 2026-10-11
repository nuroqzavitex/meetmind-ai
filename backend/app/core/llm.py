"""Pick the LLM client for the API and worker from settings."""

from pathlib import Path
from typing import Any

from app.ai.errors import LLMError
from app.ai.llm import LLMClient
from app.ai.llm.factory import make_llm
from app.ai.llm.fixture import FixtureLLM
from app.core.config import Settings


class UnconfiguredLLM:
    """Stands in when no API key is set; fails only when an LLM call is actually made."""

    async def structured(self, **_: Any) -> Any:
        raise LLMError("ANTHROPIC_API_KEY chưa được cấu hình")


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "fake":
        return FixtureLLM(Path(settings.fake_llm_dir))
    key = settings.anthropic_api_key
    if key is None:
        return UnconfiguredLLM()
    return make_llm(settings.ai_settings(), key.get_secret_value())
