"""Сборка InterviewResult: агрегация TopicAssessment в результат кандидата.

Детерминированно (без LLM) считает тройку чисел, доли покрытия (Р4) и итоговую
рекомендацию (Р5) по матрице топиков и фиксирует версии воспроизводимости
(`vacancy_version`, `model_version`, `prompt_version`). Идемпотентна: `candidate_id` —
первичный ключ `interview_result`, повторный вызов обновляет ту же запись без дубля.

Агрегация идёт по `current_status` (эффективная матрица, с учётом правок эксперта);
метрика 80% меряется отдельно по `system_status` прямо из `TopicAssessment` (TASK-022).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.candidate import Candidate
from app.models.interview_result import InterviewResult
from app.models.topic_assessment import AssessmentStatus, TopicAssessment
from app.models.vacancy import Vacancy
from app.services.coverage import compute_coverage
from app.services.matrix import TopicOutcome
from app.services.recommendation import compute_recommendation
from app.services.stop_factor import candidate_stop_factor_triggered
from app.services.topic_assessment import TOPIC_ASSESSMENT_PROMPT_VERSION


async def assemble_interview_result(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    *,
    model_version: str | None = None,
    prompt_version: str = TOPIC_ASSESSMENT_PROMPT_VERSION,
) -> InterviewResult | None:
    """Собирает/пересобирает InterviewResult кандидата (идемпотентно)."""
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        return None

    vacancy = await session.get(Vacancy, candidate.vacancy_id)
    if vacancy is None:
        return None

    assessments = list(
        await session.scalars(
            select(TopicAssessment)
            .where(TopicAssessment.candidate_id == candidate_id)
            .options(selectinload(TopicAssessment.topic))
        )
    )
    by_topic = {item.topic_id: item for item in assessments}
    outcomes = [
        TopicOutcome(
            importance=topic.importance,
            status=by_topic[topic.id].current_status
            if topic.id in by_topic
            else AssessmentStatus.NEEDS_CHECK,
        )
        for topic in vacancy.topics
    ]

    coverage = compute_coverage(outcomes)
    stop_triggered = await candidate_stop_factor_triggered(session, candidate_id)
    recommendation = compute_recommendation(outcomes, stop_factor_triggered=stop_triggered)
    resolved_model_version = model_version or get_settings().llm_model

    result = await session.get(InterviewResult, candidate_id)
    if result is None:
        result = InterviewResult(candidate_id=candidate_id)
        session.add(result)

    result.confirmed_count = coverage.confirmed_count
    result.needs_check_count = coverage.needs_check_count
    result.not_confirmed_count = coverage.not_confirmed_count
    result.mandatory_coverage = coverage.mandatory_coverage
    result.desired_coverage = coverage.desired_coverage
    result.recommendation = recommendation
    result.vacancy_version = vacancy.version
    result.model_version = resolved_model_version
    result.prompt_version = prompt_version

    await session.commit()
    await session.refresh(result)
    return result
