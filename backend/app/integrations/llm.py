"""LangChain ChatOpenAI wrapper (OpenAI-compatible protocol)."""

from __future__ import annotations

from enum import StrEnum

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import Settings, get_settings


class LLMRole(StrEnum):
    """Which configured model to use for a call."""

    QUALITY = "quality"
    FAST = "fast"


class LLMError(Exception):
    """Typed failure from the LLM integration (network, API, schema)."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class LLMResult[T](BaseModel):
    """LLM payload plus reproducibility metadata."""

    content: T
    model_version: str
    prompt_version: str


class LLMClient:
    """Thin async wrapper around LangChain ChatOpenAI.

    Provider and models are taken only from Settings / env
    (OPENAI_BASE_URL, OPENAI_API_KEY, LLM_MODEL, LLM_FAST_MODEL).
    Structured answers use native ``with_structured_output`` only.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings if settings is not None else get_settings()

    def _model_name(self, role: LLMRole) -> str:
        if role is LLMRole.FAST:
            return self._settings.llm_fast_model
        return self._settings.llm_model

    def _chat_model(self, role: LLMRole) -> ChatOpenAI:
        return ChatOpenAI(
            model=self._model_name(role),
            api_key=self._settings.openai_api_key or "not-set",
            base_url=self._settings.openai_base_url,
            temperature=0,
        )

    def _messages(
        self,
        prompt: str,
        *,
        system: str | None,
    ) -> list[SystemMessage | HumanMessage]:
        messages: list[SystemMessage | HumanMessage] = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        return messages

    async def acomplete(
        self,
        prompt: str,
        *,
        prompt_version: str,
        role: LLMRole = LLMRole.QUALITY,
        system: str | None = None,
    ) -> LLMResult[str]:
        """Run a plain-text completion and return text + version metadata."""
        model_version = self._model_name(role)
        chat = self._chat_model(role)
        try:
            response = await chat.ainvoke(self._messages(prompt, system=system))
        except Exception as exc:
            raise LLMError(f"LLM completion failed: {exc}", cause=exc) from exc

        content = response.content
        if not isinstance(content, str):
            raise LLMError(
                f"Unexpected LLM content type: {type(content).__name__}",
            )
        return LLMResult(
            content=content,
            model_version=model_version,
            prompt_version=prompt_version,
        )

    async def acomplete_structured[SchemaT: BaseModel](
        self,
        prompt: str,
        schema: type[SchemaT],
        *,
        prompt_version: str,
        role: LLMRole = LLMRole.QUALITY,
        system: str | None = None,
    ) -> LLMResult[SchemaT]:
        """Structured completion via native JSON-schema structured outputs."""
        model_version = self._model_name(role)
        chat: BaseChatModel = self._chat_model(role)
        structured = chat.with_structured_output(schema)
        try:
            raw = await structured.ainvoke(self._messages(prompt, system=system))
        except Exception as exc:
            raise LLMError(
                f"LLM structured completion failed: {exc}",
                cause=exc,
            ) from exc

        if not isinstance(raw, schema):
            raise LLMError(
                f"Structured output is not {schema.__name__}: {type(raw).__name__}",
            )
        return LLMResult(
            content=raw,
            model_version=model_version,
            prompt_version=prompt_version,
        )


class PingResponse(BaseModel):
    """Minimal schema for smoke / integration checks."""

    ok: bool = Field(description="Whether the model understood the request")
    echo: str = Field(description="Short echo of the user prompt")
