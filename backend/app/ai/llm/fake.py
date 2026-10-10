"""Deterministic in-memory LLM for tests."""

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

Response = BaseModel | dict[str, Any] | Callable[[str], BaseModel | dict[str, Any]]


class FakeLLM:
    """Scripted LLMClient; safe for concurrent use within one event loop."""

    def __init__(self, responses: dict[str, list[Response]]) -> None:
        self._responses = {agent: list(items) for agent, items in responses.items()}
        self.calls: list[tuple[str, str]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def structured(self, *, agent: str, system: str, user: str, schema: type[T]) -> T:
        self.calls.append((agent, user))
        queue = self._responses.get(agent)
        if not queue:
            raise AssertionError(f"FakeLLM has no more responses for agent '{agent}'")
        item = queue.pop(0)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0)
            if callable(item) and not isinstance(item, BaseModel):
                item = item(user)
            if isinstance(item, schema):
                return item
            data = item.model_dump() if isinstance(item, BaseModel) else item
            return schema.model_validate(data)
        finally:
            self.in_flight -= 1
