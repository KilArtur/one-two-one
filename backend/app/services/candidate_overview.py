"""Обзор кандидатов вакансии: статус обработки и тройка чисел (без AI-score)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer import Answer, AnswerProcessingStatus
from app.models.candidate import Candidate
from app.models.interview_result import InterviewResult


@dataclass(slots=True, frozen=True)
class CandidateOverview:
    """Строка списка кандидатов для рекрутера."""

    candidate_id: uuid.UUID
    candidate_status: str
    processing_status: str
    confirmed_count: int
    needs_check_count: int
    not_confirmed_count: int
    recommendation: str | None


def _derive_processing_status(statuses: set[AnswerProcessingStatus]) -> str:
    """Сводит статусы ответов кандидата к одному статусу обработки."""
    if not statuses:
        return "not_started"
    if AnswerProcessingStatus.ERROR in statuses:
        return "error"
    if statuses == {AnswerProcessingStatus.READY}:
        return "ready"
    if AnswerProcessingStatus.ANALYZING in statuses:
        return "analyzing"
    if AnswerProcessingStatus.TRANSCRIBING in statuses:
        return "transcribing"
    return "recorded"


async def list_vacancy_candidates(
    session: AsyncSession,
    vacancy_id: uuid.UUID,
    *,
    processing_status: str | None = None,
) -> list[CandidateOverview]:
    """Список кандидатов вакансии со статусом обработки, тройкой чисел и рекомендацией."""
    candidates = list(
        await session.scalars(
            select(Candidate)
            .where(Candidate.vacancy_id == vacancy_id)
            .order_by(Candidate.created_at)
        )
    )
    overviews: list[CandidateOverview] = []
    for candidate in candidates:
        answer_statuses = set(
            await session.scalars(
                select(Answer.processing_status).where(Answer.candidate_id == candidate.id)
            )
        )
        derived = _derive_processing_status(answer_statuses)
        result = await session.get(InterviewResult, candidate.id)
        overviews.append(
            CandidateOverview(
                candidate_id=candidate.id,
                candidate_status=candidate.status.value,
                processing_status=derived,
                confirmed_count=result.confirmed_count if result else 0,
                needs_check_count=result.needs_check_count if result else 0,
                not_confirmed_count=result.not_confirmed_count if result else 0,
                recommendation=result.recommendation.value if result else None,
            )
        )
    if processing_status is not None:
        overviews = [o for o in overviews if o.processing_status == processing_status]
    return overviews
