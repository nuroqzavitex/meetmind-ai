"""File-backed LLM for e2e runs: replies with `<directory>/<agent>.json`, every call."""

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.ai.errors import LLMError

T = TypeVar("T", bound=BaseModel)


class FixtureLLM:
    """LLMClient returning the same canned response per agent (not consumed like FakeLLM)."""

    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)

    async def structured(self, *, agent: str, system: str, user: str, schema: type[T]) -> T:
        path = self._dir / f"{agent}.json"
        if not path.is_file():
            raise LLMError(f"FixtureLLM: không có fixture cho agent '{agent}' ({path})")
        return schema.model_validate(json.loads(path.read_text(encoding="utf-8")))
