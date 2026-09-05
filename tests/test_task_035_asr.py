"""ASR-интеграция Whisper: транскрипт с сегментами, словарь, обработка ошибок (TASK-035)."""

import pytest
from httpx import HTTPError

from app.config import Settings
from app.integrations.asr import ASRClientError, OpenAIWhisperClient


class FakeTranscriptions:
    def __init__(self, response: object = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.captured: dict = {}

    async def create(self, **kwargs: object) -> object:
        self.captured = kwargs
        if self.error is not None:
            raise self.error
        return self.response


class _FakeAudio:
    def __init__(self, transcriptions: FakeTranscriptions) -> None:
        self.transcriptions = transcriptions


class _FakeOpenAI:
    def __init__(self, transcriptions: FakeTranscriptions) -> None:
        self.audio = _FakeAudio(transcriptions)

    async def __aenter__(self) -> "_FakeOpenAI":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _client(transcriptions: FakeTranscriptions) -> OpenAIWhisperClient:
    settings = Settings(_env_file=None, audio_api_key="test-key", asr_model="whisper-1")
    return OpenAIWhisperClient(
        settings=settings, openai_factory=lambda **_: _FakeOpenAI(transcriptions)
    )


@pytest.mark.anyio
async def test_transcribe_returns_text_and_segments() -> None:
    fake = FakeTranscriptions(
        {
            "text": "  Я проектировал схему в PostgreSQL  ",
            "segments": [
                {"text": " Я проектировал схему ", "start": 0.0, "end": 3.5},
                {"text": "в PostgreSQL", "start": 3.5, "end": 6.0},
            ],
        }
    )
    result = await _client(fake).transcribe(b"audio-bytes", filename="answer.webm")

    assert result.text == "Я проектировал схему в PostgreSQL"
    assert result.model_version == "whisper-1"
    assert result.segments == [
        {"text": "Я проектировал схему", "start": 0.0, "end": 3.5},
        {"text": "в PostgreSQL", "start": 3.5, "end": 6.0},
    ]


@pytest.mark.anyio
async def test_dictionary_applied_as_prompt() -> None:
    fake = FakeTranscriptions({"text": "ok", "segments": []})
    await _client(fake).transcribe(b"audio", terms=["Kafka", "ClickHouse", " "])

    assert "Kafka" in fake.captured["prompt"]
    assert "ClickHouse" in fake.captured["prompt"]
    assert fake.captured["model"] == "whisper-1"
    assert fake.captured["response_format"] == "verbose_json"


@pytest.mark.anyio
async def test_empty_audio_raises_typed_error() -> None:
    with pytest.raises(ASRClientError):
        await _client(FakeTranscriptions({"text": "x", "segments": []})).transcribe(b"")


@pytest.mark.anyio
async def test_provider_failure_raises_typed_error() -> None:
    fake = FakeTranscriptions(error=HTTPError("broken audio"))
    with pytest.raises(ASRClientError):
        await _client(fake).transcribe(b"broken-bytes")


@pytest.mark.anyio
async def test_missing_api_key_raises_typed_error() -> None:
    settings = Settings(_env_file=None, audio_api_key="")
    client = OpenAIWhisperClient(
        settings=settings, openai_factory=lambda **_: _FakeOpenAI(FakeTranscriptions())
    )
    with pytest.raises(ASRClientError):
        await client.transcribe(b"audio")
