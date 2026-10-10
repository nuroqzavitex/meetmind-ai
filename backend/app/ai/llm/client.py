"""LLM client protocol and Anthropic implementation."""

from typing import Protocol, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.ai.config import AISettings
from app.ai.errors import LLMError, LLMRefusal

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    async def structured(self, *, agent: str, system: str, user: str, schema: type[T]) -> T: ...


class AnthropicLLM:
    """LLMClient backed by the Anthropic API (structured outputs)."""

    def __init__(
        self, settings: AISettings, client: anthropic.AsyncAnthropic | None = None
    ) -> None:
        self._settings = settings
        self._client = client if client is not None else anthropic.AsyncAnthropic(max_retries=4)

    async def structured(self, *, agent: str, system: str, user: str, schema: type[T]) -> T:
        try:
            response = await self._client.messages.parse(
                model=self._settings.model_for(agent),
                max_tokens=self._settings.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
                extra_body={"fallbacks": "default"},
            )
        except anthropic.APIError as e:
            raise LLMError(f"Anthropic API error in agent '{agent}': {e}") from e
        except ValidationError as e:
            raise LLMError(f"Invalid structured output from agent '{agent}': {e}") from e
        if response.stop_reason == "refusal":
            raise LLMRefusal(f"Model refused request for agent '{agent}'")
        parsed = response.parsed_output
        if parsed is None:
            raise LLMError(f"No parsed output for agent '{agent}'")
        return parsed
