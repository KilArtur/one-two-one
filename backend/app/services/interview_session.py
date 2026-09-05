"""Восстановление сессии интервью после обрыва (Р11).

Прогресс кандидата считается по ответам на core-вопросы: повторный вход возвращает на
первый неотвеченный вопрос. Вопрос, недоступный из-за обрыва, помечается technically_lost,
а его топик получает needs_check (Р11: не «не подтверждено», а «требует проверки»).
Доступ ограничен сроком действия ссылки интервью (TTL).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.answer import Answer, AnswerProcessingStatus
from app.models.candidate import Candidate
from app.models.interview_link import InterviewLink
from app.models.question import Question, QuestionType
from app.models.topic import Topic
from app.services.transcription import _ensure_needs_check


@dataclass(slots=True, frozen=True)
class SessionState:
    """Состояние сессии для восстановления."""

    current_question: Question | None
    answered_count: int
    total: int
    finished: bool


async def _ensure_link_active(session: AsyncSession, candidate_id: uuid.UUID) -> None:
    """Проверяет, что у кандидата есть действующая (не истёкшая/отозванная) ссылка."""
    now = datetime.now(UTC)
    link = await session.scalar(
        select(InterviewLink)
        .where(
            InterviewLink.candidate_id == candidate_id,
            InterviewLink.revoked.is_(False),
            InterviewLink.expires_at > now,
        )
        .order_by(InterviewLink.created_at.desc())
    )
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Interview link is not active"
        )


async def _core_questions(
    session: AsyncSession, vacancy_id: uuid.UUID, candidate_id: uuid.UUID | None = None
) -> list[Question]:
    rows = await session.scalars(
        select(Question)
        .join(Topic, Question.topic_id == Topic.id)
        .where(
            Topic.vacancy_id == vacancy_id,
            or_(Question.type == QuestionType.CORE, Question.candidate_id == candidate_id)
            if candidate_id
            else Question.type == QuestionType.CORE,
        )
        .order_by(Topic.order, Question.created_at, Question.id)
    )
    return list(rows)


async def _answered_question_ids(session: AsyncSession, candidate_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await session.scalars(
        select(Answer.question_id).where(Answer.candidate_id == candidate_id)
    )
    return set(rows)


async def session_state(session: AsyncSession, candidate: Candidate) -> SessionState:
    """Возвращает текущий вопрос для продолжения (первый неотвеченный)."""
    await _ensure_link_active(session, candidate.id)
    questions = await _core_questions(session, candidate.vacancy_id, candidate.id)
    answered = await _answered_question_ids(session, candidate.id)
    current = next((q for q in questions if q.id not in answered), None)
    return SessionState(
        current_question=current,
        answered_count=len(answered),
        total=len(questions),
        finished=current is None and bool(questions),
    )


async def mark_current_technically_lost(
    session: AsyncSession, candidate: Candidate
) -> Answer | None:
    """Помечает текущий неотвеченный вопрос как technically_lost, топик → needs_check (Р11)."""
    await _ensure_link_active(session, candidate.id)
    questions = await _core_questions(session, candidate.vacancy_id, candidate.id)
    answered = await _answered_question_ids(session, candidate.id)
    current = next((q for q in questions if q.id not in answered), None)
    if current is None:
        return None

    answer = Answer(
        candidate_id=candidate.id,
        question_id=current.id,
        technically_lost=True,
        processing_status=AnswerProcessingStatus.ERROR,
    )
    session.add(answer)
    await _ensure_needs_check(session, candidate.id, current.topic_id)
    await session.commit()
    await session.refresh(answer)
    return answer
