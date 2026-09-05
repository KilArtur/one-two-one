"""Потоковая озвучка и кеш ядра (TASK-029)."""

import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import httpx2
import pytest
from openai import AsyncOpenAI

from app.config import Settings
from app.integrations.storage import S3Object, S3StorageError
from app.integrations.tts import OpenAITTSClient, TTSClientError
from app.models.question import Question, QuestionType
from app.services.question_audio import QuestionAudioService


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.reads = 0
        self.writes = 0

    async def get_object_bytes(self, key: str) -> bytes:
        self.reads += 1
        if key not in self.objects:
            raise S3StorageError("Missing", "test", key, code="NoSuchKey")
        return self.objects[key]

    async def put_object(self, key: str, data: bytes, *, content_type: str = "") -> S3Object:
        assert content_type == "audio/mpeg"
        self.objects[key] = data
        self.writes += 1
        return S3Object("test", key)


class FakeTTS:
    cache_identity = ("test-provider", "tts-1", "alloy", "mp3")

    def __init__(self) -> None:
        self.calls = 0
        self.closed = False
        self.fail = False

    async def stream_speech(self, text: str) -> AsyncGenerator[bytes, None]:
        self.calls += 1
        try:
            yield b"first"
            if self.fail:
                raise TTSClientError("failed mid-stream")
            yield b"second"
        finally:
            self.closed = True


def question(kind: QuestionType = QuestionType.CORE) -> Question:
    return Question(id=uuid.uuid4(), type=kind, text="Расскажите о своём опыте с Python.")


async def audio(service: QuestionAudioService, item: Question) -> bytes:
    return b"".join([chunk async for chunk in service.stream_audio(item)])


@pytest.mark.anyio
async def test_core_miss_then_hit_without_tts() -> None:
    tts, storage = FakeTTS(), MemoryStorage()
    service = QuestionAudioService(tts, storage)
    item = question()
    assert await audio(service, item) == b"firstsecond"
    assert await audio(QuestionAudioService(tts, storage), item) == b"firstsecond"
    assert tts.calls == 1
    assert storage.writes == 1
    assert storage.reads == 2


@pytest.mark.anyio
@pytest.mark.parametrize("kind", [QuestionType.PERSONAL, QuestionType.FOLLOW_UP])
async def test_non_core_always_generated(kind: QuestionType) -> None:
    tts, storage = FakeTTS(), MemoryStorage()
    service = QuestionAudioService(tts, storage)
    item = question(kind)
    assert await audio(service, item) == await audio(service, item) == b"firstsecond"
    assert tts.calls == 2
    assert storage.reads == storage.writes == 0


@pytest.mark.anyio
async def test_streams_before_completion_and_never_caches_partial_audio() -> None:
    tts, storage = FakeTTS(), MemoryStorage()
    service = QuestionAudioService(tts, storage)
    stream = service.stream_audio(question())
    assert await anext(stream) == b"first"
    assert not storage.objects
    await stream.aclose()
    assert tts.closed
    assert not storage.objects
    tts.fail = True
    with pytest.raises(TTSClientError):
        await audio(service, question())
    assert not storage.objects


@pytest.mark.anyio
async def test_audio_survives_failed_cache_write() -> None:
    class FullStorage(MemoryStorage):
        async def put_object(self, key: str, data: bytes, *, content_type: str = "") -> S3Object:
            raise S3StorageError("Storage full", "test", key, code="XMinioStorageFull")

    storage = FullStorage()
    assert await audio(QuestionAudioService(FakeTTS(), storage), question()) == b"firstsecond"
    assert not storage.objects


@pytest.mark.anyio
async def test_cache_error_is_not_treated_as_miss() -> None:
    class DeniedStorage(MemoryStorage):
        async def get_object_bytes(self, key: str) -> bytes:
            raise S3StorageError("Denied", "test", key, code="AccessDenied")

    tts = FakeTTS()
    with pytest.raises(S3StorageError):
        await audio(QuestionAudioService(tts, DeniedStorage()), question())
    assert tts.calls == 0


def test_cache_identity_changes_with_text_model_voice_and_provider() -> None:
    settings = Settings(_env_file=None)
    item = question()

    def key(config: Settings) -> str:
        return QuestionAudioService(OpenAITTSClient(config), MemoryStorage()).cache_key(item)

    original = key(settings)
    for field in ("tts_model", "tts_voice", "audio_base_url"):
        assert key(settings.model_copy(update={field: "different"})) != original
    assert key(settings.model_copy(update={"audio_api_key": "another-key"})) == original
    item.text += " Подробнее."
    assert key(settings) != original


@pytest.mark.anyio
@pytest.mark.parametrize("status", [200, 401, 429, 500])
async def test_sdk_uses_audio_settings_and_wraps_failures(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    requests: list[httpx2.Request] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(status, content=b"audio" if status == 200 else b"failure")

    def client(**kwargs: Any) -> AsyncOpenAI:
        return AsyncOpenAI(
            **kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handle))
        )

    monkeypatch.setattr("app.integrations.tts.AsyncOpenAI", client)
    tts = OpenAITTSClient(
        Settings(
            _env_file=None,
            audio_api_key="audio-test-key",
            audio_base_url="https://audio.test/v1",
            openai_api_key="llm-key",
        )
    )
    if status == 200:
        assert b"".join([chunk async for chunk in tts.stream_speech("Вопрос")]) == b"audio"
    else:
        with pytest.raises(TTSClientError, match="generation failed"):
            _ = [chunk async for chunk in tts.stream_speech("Вопрос")]
    assert len(requests) == 1
    assert str(requests[0].url) == "https://audio.test/v1/audio/speech"
    assert requests[0].headers["authorization"] == "Bearer audio-test-key"
    assert json.loads(requests[0].content) == {
        "model": "tts-1",
        "voice": "alloy",
        "input": "Вопрос",
        "response_format": "mp3",
    }


@pytest.mark.anyio
async def test_missing_key_and_invalid_text_fail_locally() -> None:
    tts = OpenAITTSClient(Settings(_env_file=None, audio_api_key=""))
    for text in ("", " " * 2, "a" * 4097, "Вопрос"):
        with pytest.raises(TTSClientError):
            _ = [chunk async for chunk in tts.stream_speech(text)]


@pytest.mark.anyio
@pytest.mark.parametrize("key", ["ключ", "key with space", "key\nheader"])
async def test_invalid_key_is_a_typed_configuration_error(key: str) -> None:
    tts = OpenAITTSClient(Settings(_env_file=None, audio_api_key=key))
    with pytest.raises(TTSClientError, match="AUDIO_API_KEY"):
        _ = [chunk async for chunk in tts.stream_speech("Вопрос")]


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [False, True])
async def test_sdk_empty_audio_and_stream_failure(
    monkeypatch: pytest.MonkeyPatch, failure: bool
) -> None:
    class BrokenStream(httpx2.AsyncByteStream):
        async def __aiter__(self) -> AsyncGenerator[bytes, None]:
            if failure:
                yield b"partial"
                raise httpx2.ReadError("Disconnected")
            return

    def client(**kwargs: Any) -> AsyncOpenAI:
        transport = httpx2.MockTransport(
            lambda request: httpx2.Response(200, stream=BrokenStream())
        )
        return AsyncOpenAI(**kwargs, http_client=httpx2.AsyncClient(transport=transport))

    monkeypatch.setattr("app.integrations.tts.AsyncOpenAI", client)
    tts = OpenAITTSClient(Settings(_env_file=None, audio_api_key="test-key"))
    storage = MemoryStorage()
    with pytest.raises(TTSClientError):
        await audio(QuestionAudioService(tts, storage), question())
    assert not storage.objects
