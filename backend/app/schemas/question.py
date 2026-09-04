"""Question API schemas (TASK-014)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import QuestionPattern, QuestionType


class QuestionRead(BaseModel):
    """Question as returned from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic_id: uuid.UUID
    type: QuestionType
    pattern: QuestionPattern
    text: str
    source_reason: str
    reviewed_by_expert: bool
    parent_question_id: uuid.UUID | None = None


class GenerateCoreQuestionsResponse(BaseModel):
    """Result of core-question generation (cache hit or fresh LLM)."""

    vacancy_id: uuid.UUID
    cached: bool
    model_version: str | None = None
    prompt_version: str | None = None
    questions: list[QuestionRead] = Field(default_factory=list)
