"""Схемы структурированных ответов LLM для оценки топика и стоп-факторов."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.topic_assessment import AssessmentConfidence


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


class StopFactorLLM(BaseModel):
    """Структурированный вывод LLM при проверке одного стоп-фактора (Р6)."""

    triggered_explicitly: bool = Field(
        description="Кандидат явно и однозначно подтвердил срабатывание стоп-фактора"
    )
    confidence: AssessmentConfidence = Field(description="Категориальная уверенность вывода")
    evidence_quote: str = Field(description="Точная цитата из транскрипта (или пустая строка)")
    reasoning_summary: str = Field(description="Краткое обоснование вывода")
