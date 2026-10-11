import json
import re
from pathlib import Path
from typing import Any

import pytest
from evals.runners.run_qa import main
from tests.backend.pipeline_helpers import fx

from app.ai.llm.fake import FakeLLM

pytestmark = pytest.mark.db


def _qa_answer(user: str) -> dict[str, Any]:
    for block in user.split("\n\n"):
        m = re.match(r"\[(\d+)\]", block)
        if m and "schema" in block:
            return {"answer": f"Minh dựng schema [{m.group(1)}]", "used_refs": [int(m.group(1))]}
    raise AssertionError("no context mentions schema")


def test_run_qa_smoke(migrated_db_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # migrated_db_url guarantees reachability and the `_test` name guard; run_qa resets that DB.
    monkeypatch.setenv("TEST_DATABASE_URL", migrated_db_url)
    llm = FakeLLM(
        {
            "extract": [fx("extract.json")],
            "topics": [fx("topics.json")],
            "qa_filter": [{"rewritten_query": "Ai dựng schema Postgres"}],
            "qa": [_qa_answer],
        }
    )
    code = main(
        ["--only", "qa_answer_schema_owner", "--embedder", "hash", "--report-dir", str(tmp_path)],
        llm_factory=lambda settings: llm,
    )
    assert code == 0
    reports = list(tmp_path.glob("qa-*.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert {"prompt_version", "embedder", "scores", "pass", "results"} <= report.keys()
    assert report["scores"] == {"qa_citation_accuracy": 1.0}
    assert report["pass"] is True
    assert report["results"][0]["response"]["citations"]
