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


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


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
    needle = _normalize(quote)
    texts = [_normalize(str(segment.get("text", ""))) for segment in segments]
    offset = " ".join(texts).find(needle)
    if offset < 0:
        return None
    cursor = 0
    matched = []
    for segment, text in zip(segments, texts, strict=True):
        if cursor < offset + len(needle) and cursor + len(text) > offset:
            matched.append(segment)
        cursor += len(text) + 1
    if not matched or matched[0].get("start") is None:
        return None
    return {
        "quote": quote,
        "start_sec": matched[0]["start"],
        "end_sec": matched[-1].get("end"),
        "question_id": str(question_id),
    }
