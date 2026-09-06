"""Обзор кандидатов вакансии: статус обработки и тройка чисел (без AI-score)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.answer import Answer, AnswerProcessingStatus
from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_result import InterviewResult
from app.models.topic_assessment import AssessmentStatus, TopicAssessment
from app.models.vacancy import Vacancy
from app.services.coverage import compute_coverage
from app.services.matrix import TopicOutcome


@dataclass(slots=True, frozen=True)
class CandidateOverview:
    """Строка списка кандидатов для рекрутера."""

    candidate_id: uuid.UUID
    full_name: str | None
    candidate_status: str
    processing_status: str
    confirmed_count: int
    needs_check_count: int
    not_confirmed_count: int
    recommendation: str | None
    skill_coverage: float | None
    mandatory_coverage: float | None
    desired_coverage: float | None
    mandatory_confirmed_share: float | None
    desired_confirmed_share: float | None
    mandatory_potential_share: float | None


def _derive_processing_status(statuses: set[AnswerProcessingStatus]) -> str:
    """Сводит статусы ответов кандидата к одному статусу обработки."""
    if not statuses:
        return "not_started"
    if AnswerProcessingStatus.ANALYZING in statuses:
        return "analyzing"
    if AnswerProcessingStatus.TRANSCRIBING in statuses:
        return "transcribing"
    if AnswerProcessingStatus.RECORDED in statuses:
        return "recorded"
    if AnswerProcessingStatus.READY in statuses:
        return "ready"
    return "error"


def _ratio(confirmed: int, needs_check: int, not_confirmed: int) -> float | None:
    total = confirmed + needs_check + not_confirmed
    if total == 0:
        return None
    return confirmed / total


def _as_float(value: object | None) -> float | None:
    return None if value is None else float(value)  # type: ignore[arg-type]


async def list_vacancy_candidates(
    session: AsyncSession,
    vacancy_id: uuid.UUID,
    *,
    processing_status: str | None = None,
) -> list[CandidateOverview]:
    """Список кандидатов вакансии со статусом обработки, тройкой чисел и рекомендацией."""
    vacancy = await session.scalar(
        select(Vacancy).where(Vacancy.id == vacancy_id).options(selectinload(Vacancy.topics))
    )
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

        mandatory_confirmed = (
            float(result.mandatory_coverage)
            if result is not None and result.mandatory_coverage is not None
            else None
        )
        desired_confirmed = (
            float(result.desired_coverage)
            if result is not None and result.desired_coverage is not None
            else None
        )
        mandatory_share: float | None = mandatory_confirmed
        desired_share: float | None = desired_confirmed
        potential: float | None = None

        if vacancy is not None and vacancy.topics:
            assessments = {
                row.topic_id: row
                for row in await session.scalars(
                    select(TopicAssessment).where(TopicAssessment.candidate_id == candidate.id)
                )
            }
            if assessments:
                outcomes = [
                    TopicOutcome(
                        importance=topic.importance,
                        status=assessments[topic.id].current_status
                        if topic.id in assessments
                        else AssessmentStatus.NEEDS_CHECK,
                    )
                    for topic in vacancy.topics
                ]
                coverage = compute_coverage(outcomes)
                mandatory_share = _as_float(coverage.mandatory_confirmed_share)
                desired_share = _as_float(coverage.desired_confirmed_share)
                potential = _as_float(coverage.mandatory_potential_share)
                # Р4-поля оставляем как в результате (None при спорных)
                if result is not None:
                    mandatory_confirmed = _as_float(result.mandatory_coverage)
                    desired_confirmed = _as_float(result.desired_coverage)
                else:
                    mandatory_confirmed = _as_float(coverage.mandatory_coverage)
                    desired_confirmed = _as_float(coverage.desired_coverage)
            else:
                # Без оценок не подставляем «требует проверки» на все топики.
                mandatory_share = None
                desired_share = None
                potential = None

        overviews.append(
            CandidateOverview(
                candidate_id=candidate.id,
                full_name=candidate.full_name,
                candidate_status=candidate.status.value,
                processing_status=derived,
                confirmed_count=confirmed,
                needs_check_count=needs_check,
                not_confirmed_count=not_confirmed,
                recommendation=result.recommendation.value if result else None,
                skill_coverage=_ratio(confirmed, needs_check, not_confirmed),
                mandatory_coverage=mandatory_confirmed,
                desired_coverage=desired_confirmed,
                mandatory_confirmed_share=mandatory_share,
                desired_confirmed_share=desired_share,
                mandatory_potential_share=potential,
            )
        )
    if processing_status is not None:
        overviews = [o for o in overviews if o.processing_status == processing_status]
    return overviews
