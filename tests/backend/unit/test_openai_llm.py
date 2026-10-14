from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest
from pydantic import BaseModel

from app.ai.agents.extract import ExtractOutput
from app.ai.agents.qa import QAAnswer, QAFilter
from app.ai.config import AISettings
from app.ai.errors import LLMError, LLMRefusal
from app.ai.llm.openai_client import OpenAILLM, strict_json_schema
from app.core.config import Settings
from app.core.llm import build_llm


class Out(BaseModel):
    acts: list[str] = []
    score: float = 0.5


def _completion(content: str | None, *, finish: str = "stop", refusal: str | None = None) -> Any:
    message = SimpleNamespace(content=content, refusal=refusal)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish)])


class StubAsyncOpenAI:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.kwargs: dict[str, Any] = {}

        async def create(**kwargs: Any) -> Any:
            self.kwargs = kwargs
            if error is not None:
                raise error
            return result

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


def _llm(stub: StubAsyncOpenAI) -> OpenAILLM:
    ai = AISettings(models={"default": "gpt-test", "arbitrate": "gpt-big"})
    return OpenAILLM(ai, stub)  # type: ignore[arg-type]


def _walk_keys(node: Any) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {k for v in node.values() for k in _walk_keys(v)}
    if isinstance(node, list):
        return {k for v in node for k in _walk_keys(v)}
    return set()


def test_strict_schema_requires_every_field_and_has_no_defaults() -> None:
    for model in (Out, ExtractOutput, QAFilter, QAAnswer):
        schema = strict_json_schema(model)
        assert "default" not in _walk_keys(schema), model.__name__
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])


async def test_structured_parses_json_and_sends_strict_schema() -> None:
    stub = StubAsyncOpenAI(_completion('{"acts": ["a"], "score": 0.9}'))
    out = await _llm(stub).structured(agent="arbitrate", system="sys", user="usr", schema=Out)
    assert out == Out(acts=["a"], score=0.9)
    assert stub.kwargs["model"] == "gpt-big"
    assert stub.kwargs["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]
    fmt = stub.kwargs["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["name"] == "Out"


async def test_unknown_agent_uses_default_model() -> None:
    stub = StubAsyncOpenAI(_completion('{"acts": [], "score": 0}'))
    await _llm(stub).structured(agent="extract", system="s", user="u", schema=Out)
    assert stub.kwargs["model"] == "gpt-test"


async def test_refusal_raises_llm_refusal() -> None:
    stub = StubAsyncOpenAI(_completion(None, refusal="no"))
    with pytest.raises(LLMRefusal, match="extract"):
        await _llm(stub).structured(agent="extract", system="s", user="u", schema=Out)


async def test_truncated_output_raises_llm_error() -> None:
    stub = StubAsyncOpenAI(_completion('{"acts": [', finish="length"))
    with pytest.raises(LLMError, match="max_tokens"):
        await _llm(stub).structured(agent="extract", system="s", user="u", schema=Out)


async def test_invalid_json_raises_llm_error() -> None:
    stub = StubAsyncOpenAI(_completion('{"acts": "not a list", "score": 1}'))
    with pytest.raises(LLMError, match="extract"):
        await _llm(stub).structured(agent="extract", system="s", user="u", schema=Out)


async def test_api_error_raises_llm_error() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    stub = StubAsyncOpenAI(error=openai.APIConnectionError(request=request))
    with pytest.raises(LLMError, match="OpenAI API error"):
        await _llm(stub).structured(agent="qa", system="s", user="u", schema=Out)


def test_build_llm_openai_provider() -> None:
    s = Settings(_env_file=None, llm_provider="openai", openai_api_key="sk-test")
    assert isinstance(build_llm(s), OpenAILLM)


async def test_build_llm_openai_without_key_names_openai_key() -> None:
    llm = build_llm(Settings(_env_file=None, llm_provider="openai", openai_api_key=None))
    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        await llm.structured(agent="qa", system="s", user="u", schema=QAAnswer)
