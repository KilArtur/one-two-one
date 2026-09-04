"""Схемы обмена магической ссылки кандидата на короткую JWT-сессию."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class CandidateSessionExchangeRequest(BaseModel):
    """Запрос на обмен магической ссылки кандидата на короткую JWT-сессию."""

    token: str = Field(min_length=1, max_length=255)


class CandidateSessionResponse(BaseModel):
    """Ответ обмена токена ссылки на JWT-сессию кандидата."""

    access_token: str
    token_type: str = "bearer"
    candidate_id: uuid.UUID


class CandidateSessionRead(BaseModel):
    """Текущая кандидатская сессия из Bearer JWT."""

    candidate_id: uuid.UUID
    interview_link_id: uuid.UUID
