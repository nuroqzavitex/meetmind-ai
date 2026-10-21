"""Build the production LLM client."""

import anthropic
import openai

from app.ai.config import AISettings
from app.ai.llm.client import AnthropicLLM, LLMClient
from app.ai.llm.openai_client import OpenAILLM


def make_llm(ai: AISettings, api_key: str | None) -> LLMClient:
    client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=4)
    return AnthropicLLM(ai, client)


def make_openai_llm(ai: AISettings, api_key: str, base_url: str | None = None) -> LLMClient:
    """OpenAI, or any OpenAI-compatible server (Ollama Cloud) when base_url is given."""
    client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=4)
    return OpenAILLM(ai, client)
