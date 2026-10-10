"""Configuration for the AI core."""

from pydantic import BaseModel, Field


class AISettings(BaseModel):
    """Runtime settings for LLM calls."""

    prompt_version: str = "v1"
    models: dict[str, str] = Field(
        default_factory=lambda: {"default": "claude-sonnet-5-5", "arbitrate": "claude-opus-5-5"}
    )
    max_tokens: int = 16000
    max_concurrency: int = 4

    def model_for(self, agent: str) -> str:
        return self.models.get(agent, self.models["default"])
