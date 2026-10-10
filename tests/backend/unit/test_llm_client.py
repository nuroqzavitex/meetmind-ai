import asyncio
from typing import Any

import anthropic
import httpx
import pytest
from pydantic import BaseModel, ValidationError

from app.ai.config import AISettings
from app.ai.errors import LLMError, LLMRefusal
from app.ai.llm.client import AnthropicLLM
from app.ai.llm.fake import FakeLLM
from app.ai.llm.prompts import load_prompt


class ExtractOut(BaseModel):
    acts: list[str]


class _Resp:
    def __init__(self, parsed: Any, stop_reason: str) -> None:
        self.parsed_output = parsed
        self.stop_reason = stop_reason


class _Messages:
    def __init__(self, owner: "StubAsyncAnthropic") -> None:
        self.owner = owner

    async def parse(self, **kwargs: Any) -> _Resp:
        self.owner.kwargs = kwargs
        if self.owner.error is not None:
            raise self.owner.error
        return _Resp(self.owner.parsed, self.owner.stop_reason)


class StubAsyncAnthropic:
    def __init__(self, parsed: Any, stop_reason: str, error: Exception | None = None) -> None:
        self.parsed = parsed
        self.stop_reason = stop_reason
        self.error = error
        self.kwargs: dict[str, Any] = {}
        self.messages = _Messages(self)


async def test_fake_llm_returns_validated_and_records():
    llm = FakeLLM({"extract": [{"acts": []}]})
    out = await llm.structured(agent="extract", system="s", user="u", schema=ExtractOut)
    assert out.acts == [] and llm.calls == [("extract", "u")]


async def test_fake_llm_exhausted():
    with pytest.raises(AssertionError, match="extract"):
        await FakeLLM({"extract": []}).structured(
            agent="extract", system="", user="", schema=ExtractOut
        )


async def test_fake_llm_callable_and_model_instance():
    llm = FakeLLM(
        {"a": [lambda u: {"acts": [u]}, ExtractOut(acts=["m"])]},
    )
    r1 = await llm.structured(agent="a", system="", user="hi", schema=ExtractOut)
    r2 = await llm.structured(agent="a", system="", user="x", schema=ExtractOut)
    assert r1.acts == ["hi"] and r2.acts == ["m"]


async def test_fake_llm_tracks_max_in_flight():
    llm = FakeLLM({"a": [{"acts": []}] * 3})
    await asyncio.gather(
        *[llm.structured(agent="a", system="", user="u", schema=ExtractOut) for _ in range(3)]
    )
    assert llm.max_in_flight == 3 and llm.in_flight == 0


async def test_anthropic_llm_passes_model_and_schema():
    stub = StubAsyncAnthropic(parsed=ExtractOut(acts=[]), stop_reason="end_turn")
    llm = AnthropicLLM(AISettings(), client=stub)  # type: ignore[arg-type]
    out = await llm.structured(agent="arbitrate", system="s", user="u", schema=ExtractOut)
    assert out == ExtractOut(acts=[])
    assert stub.kwargs["model"] == "claude-opus-5-5" and stub.kwargs["output_format"] is ExtractOut
    assert stub.kwargs["messages"] == [{"role": "user", "content": "u"}]
    assert stub.kwargs["extra_headers"] == {"anthropic-beta": "server-side-fallback-2026-07-01"}
    assert stub.kwargs["extra_body"] == {"fallbacks": "default"}


async def test_anthropic_llm_refusal():
    stub = StubAsyncAnthropic(parsed=None, stop_reason="refusal")
    with pytest.raises(LLMRefusal):
        await AnthropicLLM(AISettings(), client=stub).structured(  # type: ignore[arg-type]
            agent="extract", system="", user="", schema=ExtractOut
        )


async def test_anthropic_llm_none_parsed():
    stub = StubAsyncAnthropic(parsed=None, stop_reason="end_turn")
    with pytest.raises(LLMError):
        await AnthropicLLM(AISettings(), client=stub).structured(  # type: ignore[arg-type]
            agent="extract", system="", user="", schema=ExtractOut
        )


async def test_anthropic_llm_api_error_keeps_cause():
    err = anthropic.APIConnectionError(request=httpx.Request("POST", "http://x"))
    stub = StubAsyncAnthropic(parsed=None, stop_reason="", error=err)
    with pytest.raises(LLMError) as ei:
        await AnthropicLLM(AISettings(), client=stub).structured(  # type: ignore[arg-type]
            agent="extract", system="", user="", schema=ExtractOut
        )
    assert ei.value.__cause__ is err


async def test_anthropic_llm_validation_error_mapped():
    try:
        ExtractOut.model_validate({"acts": 5})
    except ValidationError as ve:
        err = ve
    stub = StubAsyncAnthropic(parsed=None, stop_reason="max_tokens", error=err)
    with pytest.raises(LLMError) as ei:
        await AnthropicLLM(AISettings(), client=stub).structured(  # type: ignore[arg-type]
            agent="extract", system="", user="", schema=ExtractOut
        )
    assert ei.value.__cause__ is err


def test_model_for_falls_back_to_default():
    s = AISettings()
    assert s.model_for("extract") == "claude-sonnet-5-5"
    assert s.model_for("arbitrate") == "claude-opus-5-5"


def test_load_prompt_existing_and_missing():
    assert "dialogue act" in load_prompt("extract", "v1")
    with pytest.raises(FileNotFoundError):
        load_prompt("extract", "v999")
