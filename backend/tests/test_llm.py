"""Tests for LangChain LLM client wrapper (TASK-007)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, Field
from pytest import MonkeyPatch

from app.config import Settings, get_settings
from app.integrations.llm import LLMClient, LLMError, LLMResult, LLMRole, PingResponse


class _SampleSchema(BaseModel):
    answer: int = Field(description="A small integer answer")


def _settings(**overrides: Any) -> Settings:
    base = {
        "openai_api_key": "test-key",
        "openai_base_url": "https://example.test/v1",
        "llm_model": "quality-model",
        "llm_fast_model": "fast-model",
    }
    base.update(overrides)
    return Settings(**base)


class _OpenAICompatibleHandler(BaseHTTPRequestHandler):
    """Minimal OpenAI-compatible /v1/chat/completions for local test_steps."""

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        body = json.loads(raw.decode())
        if body.get("response_format", {}).get("type") == "json_schema":
            content = json.dumps({"ok": True, "echo": "task-007"})
        else:
            content = "pong"
        payload = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


@pytest.fixture
def local_openai_base_url() -> Any:
    server = HTTPServer(("127.0.0.1", 0), _OpenAICompatibleHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}/v1"
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_acomplete_returns_text_and_versions() -> None:
    """Шаг 1 (unit): plain completion returns text + version metadata."""
    client = LLMClient(_settings())
    fake_response = MagicMock()
    fake_response.content = "hello from llm"

    chat = MagicMock()
    chat.ainvoke = AsyncMock(return_value=fake_response)
    client._chat_model = MagicMock(return_value=chat)  # type: ignore[method-assign]

    result = await client.acomplete(
        "Say hello",
        prompt_version="prompt-v1",
        role=LLMRole.QUALITY,
    )

    assert isinstance(result, LLMResult)
    assert result.content == "hello from llm"
    assert result.model_version == "quality-model"
    assert result.prompt_version == "prompt-v1"
    chat.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_acomplete_structured_returns_pydantic_object() -> None:
    """Шаг 2: structured output via with_structured_output, no manual JSON parse."""
    client = LLMClient(_settings())
    structured_chat = MagicMock()
    structured_chat.ainvoke = AsyncMock(return_value=_SampleSchema(answer=42))

    chat = MagicMock()
    chat.with_structured_output = MagicMock(return_value=structured_chat)
    client._chat_model = MagicMock(return_value=chat)  # type: ignore[method-assign]

    result = await client.acomplete_structured(
        "Return answer=42",
        _SampleSchema,
        prompt_version="schema-v1",
        role=LLMRole.FAST,
    )

    assert isinstance(result.content, _SampleSchema)
    assert result.content.answer == 42
    assert result.model_version == "fast-model"
    assert result.prompt_version == "schema-v1"
    chat.with_structured_output.assert_called_once_with(_SampleSchema)
    structured_chat.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_local_endpoint_plain_and_structured(
    local_openai_base_url: str,
) -> None:
    """Шаги 1–3: HTTP to OpenAI-compatible endpoint; URL/model from settings only."""
    settings = _settings(
        openai_api_key="sk-local-test",
        openai_base_url=local_openai_base_url,
        llm_model="local-quality",
        llm_fast_model="local-fast",
    )
    client = LLMClient(settings)

    text_result = await client.acomplete(
        "Reply with exactly one word: pong",
        prompt_version="task-007-local-text",
        role=LLMRole.QUALITY,
    )
    assert text_result.content == "pong"
    assert text_result.model_version == "local-quality"
    assert text_result.prompt_version == "task-007-local-text"

    structured = await client.acomplete_structured(
        'Respond with ok=true and echo="task-007"',
        PingResponse,
        prompt_version="task-007-local-structured",
        role=LLMRole.FAST,
    )
    assert isinstance(structured.content, PingResponse)
    assert structured.content.ok is True
    assert structured.content.echo == "task-007"
    assert structured.model_version == "local-fast"
    assert structured.prompt_version == "task-007-local-structured"


def test_settings_drive_provider_without_code_change(monkeypatch: MonkeyPatch) -> None:
    """Шаг 3: LLM_MODEL / OPENAI_BASE_URL come only from env/settings."""
    get_settings.cache_clear()
    monkeypatch.setenv("OPENAI_API_KEY", "local-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "local-quality")
    monkeypatch.setenv("LLM_FAST_MODEL", "local-fast")

    settings = Settings()
    client = LLMClient(settings)

    assert settings.openai_base_url == "http://127.0.0.1:11434/v1"
    assert settings.llm_model == "local-quality"
    assert settings.llm_fast_model == "local-fast"
    assert client._model_name(LLMRole.QUALITY) == "local-quality"
    assert client._model_name(LLMRole.FAST) == "local-fast"

    chat = client._chat_model(LLMRole.QUALITY)
    assert chat.model_name == "local-quality"
    assert str(chat.openai_api_base).rstrip("/") == "http://127.0.0.1:11434/v1"


@pytest.mark.asyncio
async def test_network_error_raises_typed_llm_error() -> None:
    """Шаг 4: network failure becomes LLMError; process does not crash."""
    client = LLMClient(_settings())
    chat = MagicMock()
    chat.ainvoke = AsyncMock(side_effect=ConnectionError("connection refused"))
    client._chat_model = MagicMock(return_value=chat)  # type: ignore[method-assign]

    with pytest.raises(LLMError) as exc_info:
        await client.acomplete("ping", prompt_version="v0")

    err = exc_info.value
    assert isinstance(err, LLMError)
    assert isinstance(err.cause, ConnectionError)
    assert "connection refused" in str(err)


@pytest.mark.asyncio
async def test_structured_network_error_raises_typed_llm_error() -> None:
    client = LLMClient(_settings())
    structured_chat = MagicMock()
    structured_chat.ainvoke = AsyncMock(side_effect=TimeoutError("timed out"))

    chat = MagicMock()
    chat.with_structured_output = MagicMock(return_value=structured_chat)
    client._chat_model = MagicMock(return_value=chat)  # type: ignore[method-assign]

    with pytest.raises(LLMError) as exc_info:
        await client.acomplete_structured(
            "ping",
            _SampleSchema,
            prompt_version="v0",
        )

    assert isinstance(exc_info.value.cause, TimeoutError)


@pytest.mark.asyncio
async def test_live_openrouter_if_key_usable() -> None:
    """Optional live OpenRouter check when OPENAI_API_KEY is a usable ASCII key."""
    get_settings.cache_clear()
    settings = Settings()
    key = settings.openai_api_key.strip()
    if not key or not key.isascii() or not key.startswith("sk-"):
        pytest.skip(
            "OPENAI_API_KEY missing or not a usable ASCII OpenRouter/OpenAI key"
        )

    client = LLMClient(settings)
    text_result = await client.acomplete(
        "Reply with exactly one word: pong",
        prompt_version="task-007-live-text",
        role=LLMRole.FAST,
        system="You are a terse assistant.",
    )
    assert isinstance(text_result.content, str)
    assert len(text_result.content) > 0
    assert text_result.model_version == settings.llm_fast_model

    structured = await client.acomplete_structured(
        'Respond with ok=true and echo="task-007"',
        PingResponse,
        prompt_version="task-007-live-structured",
        role=LLMRole.FAST,
        system="Return only the structured fields requested.",
    )
    assert isinstance(structured.content, PingResponse)
    assert structured.content.ok is True
    assert structured.prompt_version == "task-007-live-structured"
