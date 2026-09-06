"""Карточка результата кандидата (M7, принцип 1): матрица топиков как главный объект.

Матрица топиков (статус системы и текущий, автор правки), детерминированная рекомендация
Р5 с кодом причины, тройка чисел и доли покрытия Р4, а также разведённые слои «заявлено
в резюме» и «подтверждено в интервью». AI-score не выводится.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.answer import Answer
from app.models.candidate import Candidate
from app.models.question import Question
from app.models.topic_assessment import StatusChangeLog, TopicAssessment
from app.services.coverage import compute_coverage
from app.services.matrix import TopicOutcome
from app.services.recommendation import recommendation_with_reason


@dataclass(slots=True, frozen=True)
class ResultTopicRow:
    """Строка матрицы топиков в карточке результата."""

    topic_id: uuid.UUID
    assessment_id: uuid.UUID | None
    topic_title: str
    skill_type: str
    importance: str
    system_status: str
    current_status: str
    author: str
    reasoning_summary: str | None
    has_evidence: bool = False
    reviewable: bool = False


@dataclass(slots=True, frozen=True)
class ResultCard:
    """Карточка результата кандидата."""

    candidate_id: uuid.UUID
    recommendation: str
    recommendation_reason: str
    confirmed_count: int
    needs_check_count: int
    not_confirmed_count: int
    mandatory_coverage: Decimal | None
    desired_coverage: Decimal | None
    resume_text: str | None
    topics: list[ResultTopicRow]


async def _last_author(session: AsyncSession, assessment_id: uuid.UUID) -> str:
    """Роль последнего изменившего статус эксперта или 'system'."""
    log = await session.scalar(
        select(StatusChangeLog)
        .where(StatusChangeLog.assessment_id == assessment_id)
        .order_by(StatusChangeLog.created_at.desc())
    )
    return log.author_role.value if log is not None else "system"


async def build_result_card(session: AsyncSession, candidate_id: uuid.UUID) -> ResultCard | None:
    """Собирает карточку результата кандидата (матрица + рекомендация + coverage)."""
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        return None

    assessments = list(
        await session.scalars(
            select(TopicAssessment)
            .where(TopicAssessment.candidate_id == candidate_id)
            .options(selectinload(TopicAssessment.topic))
        )
    )
    assessments.sort(key=lambda item: item.topic.order)

    recorded_topics = set(
        await session.scalars(
            select(Question.topic_id)
            .join(Answer, Answer.question_id == Question.id)
            .where(
                Answer.candidate_id == candidate_id,
                Answer.skipped.is_(False),
                Answer.video_url.is_not(None),
            )
        )
    )

    topics: list[ResultTopicRow] = []
    outcomes: list[TopicOutcome] = []
    for assessment in assessments:
        topics.append(
            ResultTopicRow(
                topic_id=assessment.topic_id,
                assessment_id=assessment.id,
                topic_title=assessment.topic.title,
                skill_type=assessment.topic.skill_type.value,
                importance=assessment.topic.importance.value,
                system_status=assessment.system_status.value,
                current_status=assessment.current_status.value,
                author=await _last_author(session, assessment.id),
                reasoning_summary=assessment.reasoning_summary,
                has_evidence=bool(assessment.evidence),
                reviewable=bool(assessment.evidence) or assessment.topic_id in recorded_topics,
            )
        )
        outcomes.append(
            TopicOutcome(importance=assessment.topic.importance, status=assessment.current_status)
        )

    assessed_ids = {item.topic_id for item in assessments}
    for topic in candidate.vacancy.topics:
        if topic.id not in assessed_ids:
            from app.models.topic_assessment import AssessmentStatus

            topics.append(
                ResultTopicRow(
                    topic_id=topic.id,
                    assessment_id=None,
                    topic_title=topic.title,
                    skill_type=topic.skill_type.value,
                    importance=topic.importance.value,
                    system_status="needs_check",
                    current_status="needs_check",
                    author="system",
                    reasoning_summary="Обработка ответа ещё не завершена.",
                    reviewable=topic.id in recorded_topics,
                )
            )
            outcomes.append(
                TopicOutcome(
                    importance=topic.importance,
                    status=AssessmentStatus.NEEDS_CHECK,
                )
            )
    order = {topic.id: topic.order for topic in candidate.vacancy.topics}
    topics.sort(key=lambda row: order[row.topic_id])

    recommendation, reason = recommendation_with_reason(outcomes)
    coverage = compute_coverage(outcomes)

    return ResultCard(
        candidate_id=candidate_id,
        recommendation=recommendation.value,
        recommendation_reason=reason,
        confirmed_count=coverage.confirmed_count,
        needs_check_count=coverage.needs_check_count,
        not_confirmed_count=coverage.not_confirmed_count,
        mandatory_coverage=coverage.mandatory_coverage,
        desired_coverage=coverage.desired_coverage,
        resume_text=candidate.resume_text,
        topics=topics,
    )
