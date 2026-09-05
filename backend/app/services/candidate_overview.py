"""Обзор кандидатов вакансии: статус обработки и тройка чисел (без AI-score)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer import Answer, AnswerProcessingStatus
from app.models.candidate import Candidate, CandidateStatus
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
    skill_coverage: float | None
    mandatory_coverage: float | None
    desired_coverage: float | None


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


def _ratio(confirmed: int, needs_check: int, not_confirmed: int) -> float | None:
    total = confirmed + needs_check + not_confirmed
    if total == 0:
        return None
    return confirmed / total


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
        if candidate.status == CandidateStatus.SUBMITTED and derived == "ready":
            derived = "analyzing"
        result = await session.get(InterviewResult, candidate.id)
        confirmed = result.confirmed_count if result else 0
        needs_check = result.needs_check_count if result else 0
        not_confirmed = result.not_confirmed_count if result else 0
        overviews.append(
            CandidateOverview(
                candidate_id=candidate.id,
                candidate_status=candidate.status.value,
                processing_status=derived,
                confirmed_count=confirmed,
                needs_check_count=needs_check,
                not_confirmed_count=not_confirmed,
                recommendation=result.recommendation.value if result else None,
                skill_coverage=_ratio(confirmed, needs_check, not_confirmed),
                mandatory_coverage=(
                    float(result.mandatory_coverage)
                    if result is not None and result.mandatory_coverage is not None
                    else None
                ),
                desired_coverage=(
                    float(result.desired_coverage)
                    if result is not None and result.desired_coverage is not None
                    else None
                ),
            )
        )
    if processing_status is not None:
        overviews = [o for o in overviews if o.processing_status == processing_status]
    return overviews
