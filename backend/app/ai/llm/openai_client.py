"""LLMClient implementation backed by the OpenAI API (strict structured outputs)."""

import json
import re
from typing import Any, TypeVar, get_origin

import openai
from openai.lib._pydantic import to_strict_json_schema
from pydantic import BaseModel, ValidationError

from app.ai.config import AISettings
from app.ai.errors import LLMError, LLMRefusal

T = TypeVar("T", bound=BaseModel)


def _drop_defaults(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _drop_defaults(v) for k, v in node.items() if k != "default"}
    if isinstance(node, list):
        return [_drop_defaults(v) for v in node]
    return node


def strict_json_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """JSON schema accepted by OpenAI strict mode.

    The SDK makes every property required but keeps non-None defaults, which strict mode
    rejects; since the model must emit every field anyway, defaults are dropped.
    """
    result: dict[str, Any] = _drop_defaults(to_strict_json_schema(schema))
    return result


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def parse_loose(content: str, schema: type[T]) -> T:
    """Validate JSON that OpenAI-compatible servers without strict schemas (Ollama) return.

    They may wrap it in a ```json fence, or answer a one-list schema with the bare list.
    """
    fenced = _FENCE.match(content)
    text = fenced.group(1) if fenced else content
    try:
        return schema.model_validate_json(text)
    except ValidationError:
        data = json.loads(text)  # not JSON at all: let JSONDecodeError say so
        lists = [n for n, f in schema.model_fields.items() if get_origin(f.annotation) is list]
        if isinstance(data, list) and len(schema.model_fields) == 1 and lists:
            return schema.model_validate({lists[0]: data})
        raise


INVALID_OUTPUT_ATTEMPTS = 2


class OpenAILLM:
    """LLMClient backed by OpenAI chat completions with a strict JSON schema."""

    def __init__(self, settings: AISettings, client: openai.AsyncOpenAI) -> None:
        self._settings = settings
        self._client = client

    async def structured(self, *, agent: str, system: str, user: str, schema: type[T]) -> T:
        # Servers without strict schemas (Ollama) now and then emit a malformed object; a fresh
        # sample usually parses, so one invalid answer is retried before failing the whole step.
        for attempt in range(INVALID_OUTPUT_ATTEMPTS):
            content = await self._complete(agent=agent, system=system, user=user, schema=schema)
            try:
                return parse_loose(content, schema)
            except (ValidationError, ValueError) as e:
                if attempt == INVALID_OUTPUT_ATTEMPTS - 1:
                    raise LLMError(f"Invalid structured output from agent '{agent}': {e}") from e
        raise AssertionError("unreachable")

    async def _complete(self, *, agent: str, system: str, user: str, schema: type[T]) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._settings.model_for(agent),
                max_completion_tokens=self._settings.max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__,
                        "schema": strict_json_schema(schema),
                        "strict": True,
                    },
                },
            )
        except openai.APIError as e:
            raise LLMError(f"OpenAI API error in agent '{agent}': {e}") from e
        choice = response.choices[0]
        if getattr(choice.message, "refusal", None):
            raise LLMRefusal(f"Model refused request for agent '{agent}'")
        if choice.finish_reason == "length":
            raise LLMError(f"Output of agent '{agent}' was cut off at max_tokens")
        content = choice.message.content
        if not content:
            raise LLMError(f"No output for agent '{agent}'")
        return content
