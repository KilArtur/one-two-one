"""Схемы API для выпуска, просмотра и отзыва ссылки интервью."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.candidate import CandidateStatus


class InterviewLinkRead(BaseModel):
    """Ссылка интервью в ответе API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    token: str
    expires_at: datetime
    used_at: datetime | None
    revoked: bool


class CandidateInterviewSubmitResponse(BaseModel):
    """Результат отправки интервью кандидатом."""

    candidate_id: uuid.UUID
    interview_link_id: uuid.UUID
    used_at: datetime
    candidate_status: CandidateStatus
