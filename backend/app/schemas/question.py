"""Схемы вопросов интервью."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.question import QuestionPattern, QuestionType


class QuestionRead(BaseModel):
    """Вопрос в ответе API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic_id: uuid.UUID
    type: QuestionType
    pattern: QuestionPattern
    text: str
    source_reason: str | None
    reviewed_by_expert: bool


class QuestionTextUpdate(BaseModel):
    """Правка формулировки вопроса техспециалистом."""

    text: str = Field(min_length=1, max_length=2000)


class GeneratedCoreQuestion(BaseModel):
    """Структурированный ответ LLM при генерации основного вопроса топика (M2)."""

    text: str = Field(min_length=1)
    pattern: QuestionPattern
    source_reason: str = Field(min_length=1)


class PersonalizedQuestions(BaseModel):
    """Подтверждённые вопросы, раскрытые под резюме кандидата (M2)."""

    questions: list[str] = Field(
        description="Переформулированные вопросы строго в том же порядке и количестве"
    )
