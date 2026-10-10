"""Prompt loading."""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(agent: str, version: str) -> str:
    """Read ``app/ai/prompts/<agent>/<version>.md`` (UTF-8)."""
    return (_PROMPTS_DIR / agent / f"{version}.md").read_text(encoding="utf-8")
