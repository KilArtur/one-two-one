"""Потоковая озвучка через OpenAI-совместимый Speech API."""

from collections.abc import AsyncGenerator
from typing import Protocol

from httpx2 import HTTPError
from openai import APIError, AsyncOpenAI

from app.config import Settings, get_settings


class TTSClientError(Exception):
    """Не удалось получить аудио от TTS-провайдера."""


class TTSClient(Protocol):
    """Контракт потокового синтеза MP3."""

    @property
    def cache_identity(self) -> tuple[str, ...]: ...

    def stream_speech(self, text: str) -> AsyncGenerator[bytes, None]: ...


class OpenAITTSClient:
    """Асинхронный TTS-клиент с отдельными настройками аудиопровайдера."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def cache_identity(self) -> tuple[str, ...]:
        """Параметры, влияющие на содержимое кешированного MP3."""
        return (
            self._settings.audio_base_url,
            self._settings.tts_model,
            self._settings.tts_voice,
            "mp3",
        )

    async def stream_speech(self, text: str) -> AsyncGenerator[bytes, None]:
        """Отдаёт аудио по мере получения и закрывает соединение при отмене."""
        if not text.strip() or len(text) > 4096:
            raise TTSClientError("TTS text must contain 1–4096 characters")
        if not self._settings.audio_api_key:
            raise TTSClientError("AUDIO_API_KEY is not configured")
        if not self._settings.audio_api_key.isascii() or any(
            character.isspace() for character in self._settings.audio_api_key
        ):
            raise TTSClientError("AUDIO_API_KEY must be a valid API key without whitespace")
        try:
            async with AsyncOpenAI(
                api_key=self._settings.audio_api_key,
                base_url=self._settings.audio_base_url,
                timeout=self._settings.tts_timeout_seconds,
                max_retries=0,
            ) as client:
                async with client.audio.speech.with_streaming_response.create(
                    model=self._settings.tts_model,
                    voice=self._settings.tts_voice,
                    input=text,
                    response_format="mp3",
                ) as response:
                    received = False
                    async for chunk in response.iter_bytes():
                        if chunk:
                            received = True
                            yield chunk
                    if not received:
                        raise TTSClientError("TTS returned empty audio")
        except (APIError, HTTPError) as exc:
            raise TTSClientError("TTS speech generation failed") from exc
