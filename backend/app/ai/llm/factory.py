"""Build the production LLM client."""

import anthropic

from app.ai.config import AISettings
from app.ai.llm.client import AnthropicLLM, LLMClient


def make_llm(ai: AISettings, api_key: str | None) -> LLMClient:
    client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=4)
    return AnthropicLLM(ai, client)
