"""Озвучка вопросов с кешированием ядра в S3."""

import hashlib
import json
from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import Protocol

from app.integrations.storage import S3Object, S3StorageError, get_s3_storage_client
from app.integrations.tts import OpenAITTSClient, TTSClient, TTSClientError
from app.models.question import Question, QuestionType


class AudioStorage(Protocol):
    """Хранилище кешированных аудиофайлов."""

    async def get_object_bytes(self, key: str) -> bytes: ...

    async def put_object(
        self, key: str, data: bytes, *, content_type: str = "application/octet-stream"
    ) -> S3Object: ...


class QuestionAudioService:
    """Отдаёт MP3 ядра из кеша; прочие вопросы всегда синтезирует."""

    def __init__(self, tts: TTSClient, storage: AudioStorage) -> None:
        self._tts = tts
        self._storage = storage

    def cache_key(self, question: Question) -> str:
        """Изменение вопроса или настроек голоса создаёт новый объект кеша."""
        identity = json.dumps(
            [str(question.id), question.text, self._tts.cache_identity], ensure_ascii=False
        )
        digest = hashlib.sha256(identity.encode()).hexdigest()
        return f"tts/core/v1/{digest}.mp3"

    async def stream_audio(self, question: Question) -> AsyncGenerator[bytes, None]:
        """Кеширует только полностью полученное аудио core-вопросов; кеш необязателен."""
        key = self.cache_key(question) if question.type == QuestionType.CORE else None
        if key:
            try:
                cached = await self._storage.get_object_bytes(key)
            except S3StorageError as exc:
                if exc.code not in {"NoSuchKey", "404", "NotFound"}:
                    raise
            else:
                if cached:
                    yield cached
                    return

        chunks: list[bytes] = []
        received = False
        async with aclosing(self._tts.stream_speech(question.text)) as audio:
            async for chunk in audio:
                if chunk:
                    received = True
                    if key:
                        chunks.append(chunk)
                    yield chunk
        if not received:
            raise TTSClientError("TTS returned empty audio")
        if key:
            try:
                await self._storage.put_object(key, b"".join(chunks), content_type="audio/mpeg")
            except S3StorageError:
                pass


def get_question_audio_service() -> QuestionAudioService:
    """Собирает сервис с настроенными TTS и S3-провайдерами."""
    return QuestionAudioService(OpenAITTSClient(), get_s3_storage_client())
