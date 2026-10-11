import json
from pathlib import Path

import pytest
from tests.backend.pipeline_helpers import CTX_PAYMENT, FIX, PAYMENT

from app.ai.agents.qa import QAAnswer, QAFilter
from app.ai.config import AISettings
from app.ai.errors import LLMError
from app.ai.llm.fixture import FixtureLLM
from app.ai.pipeline import analyze_transcript
from app.core.config import Settings
from app.core.llm import build_llm

PAYMENT_DIR = FIX / "llm" / "payment_v2"


async def test_fixture_llm_returns_same_response_every_call(tmp_path: Path) -> None:
    (tmp_path / "qa.json").write_text(
        json.dumps({"answer": "Chốt Postgres [1].", "used_refs": [1]}), encoding="utf-8"
    )
    llm = FixtureLLM(tmp_path)
    a = await llm.structured(agent="qa", system="s", user="u1", schema=QAAnswer)
    b = await llm.structured(agent="qa", system="s", user="u2", schema=QAAnswer)
    assert a == b
    assert a.used_refs == [1]


async def test_fixture_llm_missing_agent_raises_llm_error(tmp_path: Path) -> None:
    with pytest.raises(LLMError, match="agent 'topics'"):
        await FixtureLLM(tmp_path).structured(
            agent="topics", system="s", user="u", schema=QAAnswer
        )


def test_build_llm_fake_provider(tmp_path: Path) -> None:
    s = Settings(_env_file=None, llm_provider="fake", fake_llm_dir=str(tmp_path))
    assert isinstance(build_llm(s), FixtureLLM)


async def test_build_llm_without_key_is_unconfigured() -> None:
    llm = build_llm(Settings(_env_file=None, anthropic_api_key=None))
    with pytest.raises(LLMError):
        await llm.structured(agent="qa", system="s", user="u", schema=QAAnswer)


def test_payment_v2_fixture_dir_has_all_pipeline_agents() -> None:
    for name in ("extract.json", "topics.json", "qa_filter.json", "qa.json"):
        assert (PAYMENT_DIR / name).is_file(), name
    QAAnswer.model_validate_json((PAYMENT_DIR / "qa.json").read_text(encoding="utf-8"))
    QAFilter.model_validate_json((PAYMENT_DIR / "qa_filter.json").read_text(encoding="utf-8"))


async def test_pipeline_with_fixture_llm_payment_v2() -> None:
    result = await analyze_transcript(
        ctx=CTX_PAYMENT,
        filename="payment_v2.txt",
        data=PAYMENT,
        llm=FixtureLLM(PAYMENT_DIR),
        settings=AISettings(),
    )
    decisions = [i for i in result.items if i.type == "decision"]
    assert len(decisions) == 1
    assert "Postgres" in decisions[0].content
