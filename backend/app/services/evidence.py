"""Привязка цитаты LLM к таймкоду из сегментов транскрипта (evidence).

Сегмент транскрипта — словарь с ключами `text`, `start`, `end` (секунды). Evidence —
цитата + таймкод + `question_id`. Таймкод берётся из реальных сегментов, а не из ответа
модели, чтобы не полагаться на «выдуманные» моделью числа.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from typing import Any

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _WORD_RE.findall(text)}


def locate_evidence(
    segments: Sequence[dict[str, Any]] | None,
    quote: str,
    *,
    question_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Находит сегмент с цитатой и возвращает evidence с таймкодом (или None)."""
    quote = (quote or "").strip()
    if not quote:
        return None

    segments = list(segments or [])
    needle = quote.lower()

    best_segment: dict[str, Any] | None = None
    best_overlap = 0
    quote_tokens = _tokens(quote)

    for segment in segments:
        text = str(segment.get("text", ""))
        haystack = text.lower()
        if needle and (needle in haystack or (haystack and haystack in needle)):
            best_segment = segment
            break
        overlap = len(quote_tokens & _tokens(text))
        if overlap > best_overlap:
            best_overlap = overlap
            best_segment = segment

    if best_segment is None:
        best_segment = segments[0] if segments else {}

    return {
        "quote": quote,
        "start_sec": best_segment.get("start"),
        "end_sec": best_segment.get("end"),
        "question_id": str(question_id),
    }
