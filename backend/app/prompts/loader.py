"""Load versioned prompts from markdown files under repo ``prompts/``."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# backend/app/prompts/loader.py → repo root is parents[3]
_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
_VERSION_RE = re.compile(
    r"<!--\s*prompt_version:\s*(\S+)\s*-->",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class LoadedPrompt:
    """Prompt body plus its declared version string."""

    name: str
    body: str
    version: str


@lru_cache
def load_prompt(name: str) -> LoadedPrompt:
    """Load ``prompts/{name}.md``; version from HTML comment or file stem."""
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        msg = f"Prompt file not found: {path}"
        raise FileNotFoundError(msg)

    raw = path.read_text(encoding="utf-8")
    match = _VERSION_RE.search(raw)
    version = match.group(1) if match else name
    body = _VERSION_RE.sub("", raw, count=1).strip()
    return LoadedPrompt(name=name, body=body, version=version)
