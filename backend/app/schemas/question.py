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


class PersonalizedQuestion(BaseModel):
    """Один вопрос топика, раскрытый под конкретную деталь резюме кандидата (M2)."""

    topic: str = Field(description="Название топика из входа — для сверки порядка")
    resume_detail: str = Field(
        default="",
        description=(
            "Конкретный проект, технология или роль из резюме, относящаяся ИМЕННО к этому "
            "топику. Пустая строка, если в резюме нет ничего по теме топика."
        ),
    )
    question: str = Field(
        min_length=1,
        description=(
            "Один вопрос, проверяющий то же требование топика, но опирающийся на resume_detail. "
            "Если resume_detail пуст — исходный вопрос без изменений."
        ),
    )


class PersonalizedQuestions(BaseModel):
    """Подтверждённые вопросы, раскрытые под резюме кандидата (M2)."""

    items: list[PersonalizedQuestion] = Field(
        description=(
            "По одному элементу на каждый входной вопрос, строго в том же порядке и количестве"
        )
    )
