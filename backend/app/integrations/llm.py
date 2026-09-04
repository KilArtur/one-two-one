"""Обёртка LLM-клиента через LangChain ChatOpenAI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Generic, TypeVar

from httpx import HTTPError
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from openai import APIError
from pydantic import BaseModel

from app.config import Settings, get_settings

SchemaT = TypeVar("SchemaT", bound=BaseModel)
ChatModelFactory = Callable[..., Any]


@dataclass(slots=True, frozen=True)
class LLMInvocationResult(Generic[SchemaT]):
    """Результат вызова модели вместе с версиями воспроизводимости."""

    content: str | SchemaT
    model_version: str
    prompt_version: str


@dataclass(slots=True, frozen=True)
class LLMClientError(Exception):
    """Типизированная ошибка провайдера LLM."""

    message: str
    model_name: str
    prompt_version: str
    provider_base_url: str

    def __str__(self) -> str:
        return self.message


class LangChainLLMClient:
    """Асинхронный клиент поверх LangChain `ChatOpenAI`."""

    def __init__(
        self,
        settings: Settings | None = None,
        chat_model_factory: ChatModelFactory = ChatOpenAI,
    ) -> None:
        self._settings = settings or get_settings()
        self._chat_model_factory = chat_model_factory

    async def generate_text(
        self,
        prompt: LanguageModelInput,
        *,
        prompt_version: str,
        use_fast_model: bool = False,
    ) -> LLMInvocationResult[str]:
        """Возвращает текстовый ответ модели."""
        model_name = self._resolve_model_name(use_fast_model=use_fast_model)
        model = self._build_model(model_name)

        try:
            response = await model.ainvoke(prompt)
        except Exception as exc:
            raise self._map_error(
                exc,
                model_name=model_name,
                prompt_version=prompt_version,
            ) from exc

        return LLMInvocationResult(
            content=self._extract_text(response),
            model_version=self._extract_model_version(response, requested_model=model_name),
            prompt_version=prompt_version,
        )

    async def generate_structured(
        self,
        prompt: LanguageModelInput,
        *,
        schema: type[SchemaT],
        prompt_version: str,
        use_fast_model: bool = False,
    ) -> LLMInvocationResult[SchemaT]:
        """Возвращает ответ модели, валидированный native structured outputs."""
        model_name = self._resolve_model_name(use_fast_model=use_fast_model)
        model = self._build_model(model_name)
        structured_model = model.with_structured_output(
            schema,
            method="json_schema",
            strict=True,
            include_raw=True,
        )

        try:
            response = await structured_model.ainvoke(prompt)
        except Exception as exc:
            raise self._map_error(
                exc,
                model_name=model_name,
                prompt_version=prompt_version,
            ) from exc

        parsed = response["parsed"]
        raw_message = response["raw"]

        return LLMInvocationResult(
            content=parsed,
            model_version=self._extract_model_version(raw_message, requested_model=model_name),
            prompt_version=prompt_version,
        )

    def _build_model(self, model_name: str) -> ChatOpenAI:
        return self._chat_model_factory(
            model=model_name,
            api_key=self._settings.openai_api_key,
            base_url=self._settings.openai_base_url,
            default_headers=self._settings.openai_default_headers,
            timeout=self._settings.llm_timeout_seconds,
            max_retries=0,
        )

    def _resolve_model_name(self, *, use_fast_model: bool) -> str:
        return self._settings.llm_fast_model if use_fast_model else self._settings.llm_model

    def _map_error(
        self,
        exc: Exception,
        *,
        model_name: str,
        prompt_version: str,
    ) -> LLMClientError:
        if isinstance(exc, (APIError, HTTPError, TimeoutError)):
            message = "LLM provider request failed"
        else:
            message = "LLM invocation failed"

        return LLMClientError(
            message=message,
            model_name=model_name,
            prompt_version=prompt_version,
            provider_base_url=self._settings.openai_base_url,
        )

    @staticmethod
    def _extract_model_version(response: AIMessage, *, requested_model: str) -> str:
        model_name = response.response_metadata.get("model_name")
        if isinstance(model_name, str) and model_name:
            return model_name
        return requested_model

    @staticmethod
    def _extract_text(response: AIMessage) -> str:
        if isinstance(response.content, str):
            return response.content

        if hasattr(response, "text"):
            text_value = response.text()
            if isinstance(text_value, str):
                return text_value

        raise ValueError("LLM response does not contain text content")


@lru_cache
def get_llm_client() -> LangChainLLMClient:
    """Возвращает кешированный LLM-клиент приложения."""
    return LangChainLLMClient()
