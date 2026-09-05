"""Детерминированные продуктовые метрики без персональных баллов (раздел 11.2)."""

import uuid
from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel
from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer import Answer, AnswerProcessingStatus
from app.models.candidate import Candidate, CandidateStatus
from app.models.topic_assessment import AssessmentStatus, StatusChangeLog, TopicAssessment

STATUSES = (
    AssessmentStatus.CONFIRMED,
    AssessmentStatus.NEEDS_CHECK,
    AssessmentStatus.NOT_CONFIRMED,
)
COMPLETED = (CandidateStatus.SUBMITTED, CandidateStatus.PROCESSED, CandidateStatus.REVIEWED)


@dataclass(frozen=True)
class TopicSnapshot:
    system: str
    current: str
    reviewed: bool


@dataclass(frozen=True)
class InterviewSnapshot:
    started: bool
    completed: bool
    technical_failure: bool


class Share(BaseModel):
    count: int
    total: int
    share: float | None


class Direction(BaseModel):
    from_status: str
    to_status: str
    count: int


class ProductMetrics(BaseModel):
    system_statuses: dict[str, Share]
    current_statuses: dict[str, Share]
    reviewed_topics: int
    changed_after_review: Share
    disputed_changed_after_review: Share
    review_directions: list[Direction]
    completion: Share
    technical_failures: Share


def fraction(count: int, total: int) -> Share:
    return Share(count=count, total=total, share=count / total if total else None)


def compute_metrics(
    topics: list[TopicSnapshot], interviews: list[InterviewSnapshot]
) -> ProductMetrics:
    """Считает доли с явными знаменателями; пустая выборка даёт null."""
    system = Counter(t.system for t in topics if t.system in STATUSES)
    current = Counter(t.current for t in topics if t.current in STATUSES)
    reviewed = [t for t in topics if t.reviewed and t.system in STATUSES and t.current in STATUSES]
    changed = [t for t in reviewed if t.current != t.system]
    disputed = [t for t in topics if t.system == AssessmentStatus.NEEDS_CHECK]
    directions = Counter((t.system, t.current) for t in changed)
    started = [i for i in interviews if i.started]
    return ProductMetrics(
        system_statuses={s: fraction(system[s], sum(system.values())) for s in STATUSES},
        current_statuses={s: fraction(current[s], sum(current.values())) for s in STATUSES},
        reviewed_topics=len(reviewed),
        changed_after_review=fraction(len(changed), len(reviewed)),
        disputed_changed_after_review=fraction(
            sum(t.system == AssessmentStatus.NEEDS_CHECK for t in changed), len(disputed)
        ),
        review_directions=[
            Direction(from_status=old, to_status=new, count=count)
            for (old, new), count in sorted(directions.items())
        ],
        completion=fraction(sum(i.completed for i in started), len(started)),
        technical_failures=fraction(sum(i.technical_failure for i in started), len(started)),
    )


async def load_metrics(
    session: AsyncSession, vacancy_id: uuid.UUID | None = None
) -> ProductMetrics:
    """Читает только статусы и флаги; повторные ревью/ошибки не дублируют объекты."""
    reviewed = exists(
        select(StatusChangeLog.id).where(
            StatusChangeLog.assessment_id == TopicAssessment.id,
        )
    )
    topic_query = select(
        TopicAssessment.system_status, TopicAssessment.current_status, reviewed
    ).join(Candidate)
    has_answer = exists(select(Answer.id).where(Answer.candidate_id == Candidate.id))
    failed = exists(
        select(Answer.id).where(
            Answer.candidate_id == Candidate.id,
            or_(
                Answer.technically_lost.is_(True),
                Answer.processing_status == AnswerProcessingStatus.ERROR,
            ),
        )
    )
    interview_query = select(Candidate.status, has_answer, failed)
    if vacancy_id is not None:
        topic_query = topic_query.where(Candidate.vacancy_id == vacancy_id)
        interview_query = interview_query.where(Candidate.vacancy_id == vacancy_id)
    topics = [
        TopicSnapshot(system, current, bool(was_reviewed))
        for system, current, was_reviewed in (await session.execute(topic_query)).all()
    ]
    interviews = [
        InterviewSnapshot(
            status != CandidateStatus.INVITED or bool(answer), status in COMPLETED, bool(failure)
        )
        for status, answer, failure in (await session.execute(interview_query)).all()
    ]
    return compute_metrics(topics, interviews)
