"""Схемы структурированных ответов LLM для оценки топика и решений по интервью."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.topic_assessment import AssessmentConfidence, AssessmentStatus


class TopicAssessmentLLM(BaseModel):
    """Структурированный вывод LLM при оценке одного топика по транскрипту (Р13/Р16)."""

    correctness: bool = Field(description="Ответ технически корректен по сути требования топика")
    example: bool = Field(description="Есть конкретный практический пример")
    personal_contribution: bool = Field(description="Различим личный вклад кандидата")
    confidence: AssessmentConfidence = Field(description="Категориальная уверенность оценки")
    explicit_no_experience: bool = Field(description="Кандидат явно сказал об отсутствии опыта")
    technical_error: bool = Field(description="Существенная техническая ошибка по сути требования")
    evidence_quote: str = Field(description="Точная цитата из транскрипта (или пустая строка)")
    reasoning_summary: str = Field(description="Краткое обоснование вывода")


class TopicStatusChangeRequest(BaseModel):
    """Смена статуса топика экспертом с обязательным комментарием (Р21)."""

    new_status: AssessmentStatus
    comment: str = Field(min_length=1, max_length=2000)

    @field_validator("comment")
    @classmethod
    def nonblank_comment(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Comment must not be blank")
        return value.strip()


class TopicAssessmentRead(BaseModel):
    """Оценка топика в ответе API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    topic_id: uuid.UUID
    system_status: AssessmentStatus
    current_status: AssessmentStatus
    confidence: AssessmentConfidence
    reviewer_comment: str | None


class ReviewQueueItem(BaseModel):
    """Спорный топик в очереди ревью."""

    model_config = ConfigDict(from_attributes=True)

    assessment_id: uuid.UUID
    candidate_id: uuid.UUID
    topic_id: uuid.UUID
    topic_title: str
    skill_type: str
    confidence: AssessmentConfidence
    current_status: AssessmentStatus
    reasoning_summary: str | None


class FollowupDecisionLLM(BaseModel):
    """Структурированное решение быстрого LLM об уточняющем вопросе (M4/Р12)."""

    answer_sufficient: bool = Field(description="Статус топика уже определяется уверенно")
    explicit_no_experience: bool = Field(description="Кандидат явно сказал об отсутствии опыта")
    adds_new_information: bool = Field(description="Последний ответ добавил новую информацию")
    needs_clarification: bool = Field(description="Ответ общий / нет примера / неясен вклад")
    followup_question: str = Field(description="Уточняющий вопрос в рамках топика (или пусто)")
