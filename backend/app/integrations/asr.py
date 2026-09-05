"""ASR-интеграция через OpenAI-совместимый Whisper (транскрипт с таймкодами фраз).

Пользовательский словарь вакансии передаётся как `prompt` — так Whisper смещается к
техническим терминам/англицизмам/аббревиатурам. Возвращает транскрипт и сегменты с
таймкодами на уровне фраз (ключи `text`/`start`/`end`), пригодные для evidence.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from httpx import HTTPError
from openai import APIError, AsyncOpenAI

from app.config import Settings, get_settings

OpenAIFactory = Callable[..., AsyncOpenAI]


class ASRClientError(Exception):
    """Не удалось получить транскрипт от ASR-провайдера."""


@dataclass(slots=True, frozen=True)
class TranscriptionResult:
    """Транскрипт ответа с сегментами и версией модели."""

    text: str
    segments: list[dict[str, Any]]
    model_version: str


class OpenAIWhisperClient:
    """Асинхронный ASR-клиент поверх аудиопровайдера (OpenAI Whisper)."""

    def __init__(
        self, settings: Settings | None = None, openai_factory: OpenAIFactory = AsyncOpenAI
    ) -> None:
        self._settings = settings or get_settings()
        self._openai_factory = openai_factory

    async def transcribe(
        self,
        audio: bytes,
        *,
        filename: str = "answer.webm",
        terms: Sequence[str] | None = None,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Транскрибирует аудио и возвращает текст + сегменты с таймкодами."""
        if not audio:
            raise ASRClientError("Audio payload is empty")
        if not self._settings.audio_api_key:
            raise ASRClientError("AUDIO_API_KEY is not configured")

        prompt = ", ".join(term.strip() for term in (terms or []) if term.strip()) or None
        try:
            async with self._openai_factory(
                api_key=self._settings.audio_api_key,
                base_url=self._settings.audio_base_url,
                timeout=self._settings.asr_timeout_seconds,
                max_retries=0,
            ) as client:
                response = await client.audio.transcriptions.create(
                    model=self._settings.asr_model,
                    file=(filename, audio),
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                    prompt=prompt,
                    language=language,
                )
        except (APIError, HTTPError, TimeoutError) as exc:
            raise ASRClientError("ASR transcription request failed") from exc

        return TranscriptionResult(
            text=(_get(response, "text") or "").strip(),
            segments=_normalize_segments(_get(response, "segments")),
            model_version=self._settings.asr_model,
        )


def _get(source: Any, key: str) -> Any:
    """Читает поле из pydantic-модели SDK или из словаря."""
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _normalize_segments(segments: Any) -> list[dict[str, Any]]:
    """Приводит сегменты к виду {text, start, end} на уровне фраз."""
    result: list[dict[str, Any]] = []
    for segment in segments or []:
        text = _get(segment, "text")
        start = _get(segment, "start")
        end = _get(segment, "end")
        if text is None:
            continue
        result.append(
            {
                "text": str(text).strip(),
                "start": float(start) if start is not None else None,
                "end": float(end) if end is not None else None,
            }
        )
    return result


@lru_cache
def get_asr_client() -> OpenAIWhisperClient:
    """Возвращает кешированный ASR-клиент приложения."""
    return OpenAIWhisperClient()
