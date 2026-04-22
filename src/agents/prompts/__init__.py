"""Agent system prompts loaded from adjacent markdown files."""

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Return the system prompt text for the given agent name.

    `name` maps to `src/agents/prompts/{name}.md`.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")
