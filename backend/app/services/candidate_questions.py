"""Отбор вопросов кандидата: персональный вопрос вытесняет ядро своего топика."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, and_, or_, select

from app.models.question import Question, QuestionType
from app.models.topic import Topic


def candidate_questions_stmt(
    candidate_id: uuid.UUID, vacancy_id: uuid.UUID
) -> Select[tuple[Question]]:
    """Вопросы кандидата в порядке прохождения: ядро, персональные и уточнения."""
    personalized_topics = select(Question.topic_id).where(
        Question.candidate_id == candidate_id,
        Question.type == QuestionType.PERSONAL,
    )
    return (
        select(Question)
        .join(Topic, Question.topic_id == Topic.id)
        .where(
            Topic.vacancy_id == vacancy_id,
            or_(
                and_(
                    Question.type == QuestionType.CORE,
                    Question.topic_id.not_in(personalized_topics),
                ),
                Question.candidate_id == candidate_id,
            ),
        )
        .order_by(Topic.order, Question.created_at, Question.id)
    )
