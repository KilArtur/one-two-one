"""Тесты TASK-007: LangChain LLM client wrapper."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from httpx import ConnectError, Request
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from app.config import Settings
from app.integrations import LangChainLLMClient, LLMClientError


class CandidateSignal(BaseModel):
    """Схема structured output для smoke-теста клиента."""

    topic: str = Field(description="Requirement topic")
    supported: bool = Field(description="Whether evidence supports the topic")


@dataclass
class StructuredRunnableStub:
    """Заглушка runnable, который возвращает structured output."""

    response: dict[str, object]

    async def ainvoke(self, prompt: object) -> dict[str, object]:
        return self.response


class ChatOpenAIStub:
    """Заглушка `ChatOpenAI` для unit-тестов клиента."""

    instances: list["ChatOpenAIStub"] = []
    next_text_response: AIMessage | Exception | None = None
    next_structured_response: dict[str, object] | Exception | None = None

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.prompts: list[object] = []
        self.structured_calls: list[dict[str, object]] = []
        ChatOpenAIStub.instances.append(self)

    async def ainvoke(self, prompt: object) -> AIMessage:
        self.prompts.append(prompt)
        response = ChatOpenAIStub.next_text_response
        if isinstance(response, Exception):
            raise response
        assert isinstance(response, AIMessage)
        return response

    def with_structured_output(
        self,
        schema: type[BaseModel],
        **kwargs: object,
    ) -> StructuredRunnableStub:
        self.structured_calls.append({"schema": schema, **kwargs})
        response = ChatOpenAIStub.next_structured_response
        if isinstance(response, Exception):
            raise response
        assert isinstance(response, dict)
        return StructuredRunnableStub(response=response)


@pytest.fixture(autouse=True)
def reset_stub_state() -> None:
    """Сбрасывает состояние заглушки между тестами."""
    ChatOpenAIStub.instances.clear()
    ChatOpenAIStub.next_text_response = None
    ChatOpenAIStub.next_structured_response = None


def build_client() -> LangChainLLMClient:
    """Создаёт клиент с тестовыми настройками."""
    settings = Settings(
        openai_api_key="test-key",
        openai_base_url="https://router.example/v1",
        openai_default_headers={"X-Mlp-Provider": "openrouter"},
        llm_model="quality-model",
        llm_fast_model="fast-model",
        llm_timeout_seconds=12.5,
    )
    return LangChainLLMClient(settings=settings, chat_model_factory=ChatOpenAIStub)


@pytest.mark.anyio
async def test_generate_text_uses_quality_model_and_returns_versions() -> None:
    """Клиент берёт quality model по умолчанию и отдаёт model/prompt versions."""
    ChatOpenAIStub.next_text_response = AIMessage(
        content="coverage ready",
        response_metadata={"model_name": "quality-model-2026-09-01"},
    )
    client = build_client()

    result = await client.generate_text(
        [("system", "You are strict."), ("human", "Summarize candidate evidence.")],
        prompt_version="coverage-v1",
    )

    assert result.content == "coverage ready"
    assert result.model_version == "quality-model-2026-09-01"
    assert result.prompt_version == "coverage-v1"
    assert ChatOpenAIStub.instances[0].kwargs["model"] == "quality-model"
    assert ChatOpenAIStub.instances[0].kwargs["base_url"] == "https://router.example/v1"
    assert ChatOpenAIStub.instances[0].kwargs["api_key"] == "test-key"
    assert ChatOpenAIStub.instances[0].kwargs["default_headers"] == {"X-Mlp-Provider": "openrouter"}
    assert ChatOpenAIStub.instances[0].kwargs["timeout"] == 12.5


@pytest.mark.anyio
async def test_generate_text_uses_fast_model_when_requested() -> None:
    """Для hot path клиент переключается на fast model без правок кода."""
    ChatOpenAIStub.next_text_response = AIMessage(
        content="fast answer",
        response_metadata={},
    )
    client = build_client()

    result = await client.generate_text(
        "Answer immediately.",
        prompt_version="follow-up-v2",
        use_fast_model=True,
    )

    assert result.content == "fast answer"
    assert result.model_version == "fast-model"
    assert ChatOpenAIStub.instances[0].kwargs["model"] == "fast-model"


@pytest.mark.anyio
async def test_generate_structured_uses_json_schema_native_output() -> None:
    """Structured output идёт через `with_structured_output(..., method=\"json_schema\")`."""
    parsed = CandidateSignal(topic="Python", supported=True)
    ChatOpenAIStub.next_structured_response = {
        "parsed": parsed,
        "raw": AIMessage(
            content="",
            response_metadata={"model_name": "quality-model-structured-2026-09-01"},
        ),
    }
    client = build_client()

    result = await client.generate_structured(
        "Extract coverage for the Python topic.",
        schema=CandidateSignal,
        prompt_version="topic-assessment-v1",
    )

    assert result.content == parsed
    assert result.model_version == "quality-model-structured-2026-09-01"
    assert result.prompt_version == "topic-assessment-v1"
    assert ChatOpenAIStub.instances[0].structured_calls == [
        {
            "schema": CandidateSignal,
            "method": "json_schema",
            "strict": True,
            "include_raw": True,
        }
    ]


@pytest.mark.anyio
async def test_generate_text_wraps_network_errors_into_typed_exception() -> None:
    """Сетевые ошибки провайдера превращаются в `LLMClientError`."""
    ChatOpenAIStub.next_text_response = ConnectError(
        "network down",
        request=Request("POST", "https://router.example/v1/chat/completions"),
    )
    client = build_client()

    with pytest.raises(LLMClientError) as exc_info:
        await client.generate_text("Ping.", prompt_version="health-v1")

    error = exc_info.value
    assert error.message == "LLM provider request failed"
    assert error.model_name == "quality-model"
    assert error.prompt_version == "health-v1"
    assert error.provider_base_url == "https://router.example/v1"
