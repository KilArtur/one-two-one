"""Единый загрузчик промптов из каталога `prompts/` (промпты не хардкодятся в коде)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


@lru_cache
def load_prompt(name: str) -> str:
    """Возвращает текст промпта `prompts/<name>.md`."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")
