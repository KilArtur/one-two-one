"""Ревью ядра вопросов техспециалистом: правка текста и обязательное подтверждение."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question, QuestionType
from app.models.topic import Topic
from app.models.vacancy import Vacancy

QUESTIONS_NOT_APPROVED = (
    "Техспециалист ещё не подтвердил список вопросов вакансии — интервью не запускается."
)


class QuestionsIncompleteError(Exception):
    """Ядро сгенерировано не на все топики вакансии."""


async def list_core_questions(session: AsyncSession, vacancy_id: uuid.UUID) -> list[Question]:
    """Возвращает ядро вопросов вакансии в порядке топиков."""
    rows = await session.scalars(
        select(Question)
        .join(Topic, Question.topic_id == Topic.id)
        .where(Topic.vacancy_id == vacancy_id, Question.type == QuestionType.CORE)
        .order_by(Topic.order, Question.created_at)
    )
    return list(rows)


async def update_question_text(
    session: AsyncSession, vacancy_id: uuid.UUID, question_id: uuid.UUID, text: str
) -> Question | None:
    """Заменяет формулировку core-вопроса; подтверждение при этом снимается."""
    question = await session.scalar(
        select(Question)
        .join(Topic, Question.topic_id == Topic.id)
        .where(
            Question.id == question_id,
            Topic.vacancy_id == vacancy_id,
            Question.type == QuestionType.CORE,
        )
    )
    if question is None:
        return None
    question.text = text
    question.reviewed_by_expert = False
    await session.commit()
    await session.refresh(question)
    return question


async def approve_core_questions(
    session: AsyncSession, vacancy_id: uuid.UUID
) -> list[Question] | None:
    """Подтверждает ядро целиком: интервью запускается только после этого."""
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None:
        return None
    questions = await list_core_questions(session, vacancy_id)
    covered = {question.topic_id for question in questions}
    if not vacancy.topics or covered != {topic.id for topic in vacancy.topics}:
        raise QuestionsIncompleteError
    for question in questions:
        question.reviewed_by_expert = True
    await session.commit()
    return questions


async def questions_approved(session: AsyncSession, vacancy_id: uuid.UUID) -> bool:
    """True, если на каждый топик есть подтверждённый техспециалистом вопрос."""
    topics_count = await session.scalar(
        select(func.count()).select_from(Topic).where(Topic.vacancy_id == vacancy_id)
    )
    if not topics_count:
        return False
    approved_topics = await session.scalar(
        select(func.count(func.distinct(Question.topic_id)))
        .join(Topic, Question.topic_id == Topic.id)
        .where(
            Topic.vacancy_id == vacancy_id,
            Question.type == QuestionType.CORE,
            Question.reviewed_by_expert.is_(True),
        )
    )
    return approved_topics == topics_count
