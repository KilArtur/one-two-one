"""Восстановление сессии после обрыва Р11: resume, technically_lost, TTL (TASK-033)."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.answer import Answer, AnswerProcessingStatus
from app.models.candidate import Candidate
from app.models.interview_link import InterviewLink
from app.models.question import Question, QuestionPattern, QuestionType
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.topic_assessment import AssessmentStatus, TopicAssessment
from app.models.vacancy import Vacancy, VacancyGrade
from app.services.interview_session import mark_current_technically_lost, session_state


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        yield db
    await engine.dispose()


async def _seed(
    session: AsyncSession, *, answered: int = 2, expires_in_days: int = 7
) -> tuple[Candidate, list[Question]]:
    vacancy = Vacancy(id=uuid.uuid4(), title="Backend", grade=VacancyGrade.MIDDLE)
    vacancy.lineage_id = vacancy.id
    candidate = Candidate(vacancy_id=vacancy.id)
    session.add_all([vacancy, candidate])
    await session.flush()
    session.add(
        InterviewLink(
            candidate_id=candidate.id,
            token=str(uuid.uuid4()),
            expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
        )
    )
    questions: list[Question] = []
    for i in range(3):
        topic = Topic(
            vacancy_id=vacancy.id, title=f"T{i}", skill_type=SkillType.HARD,
            importance=TopicImportance.MANDATORY, order=i,
        )
        session.add(topic)
        await session.flush()
        q = Question(
            topic_id=topic.id, type=QuestionType.CORE, pattern=QuestionPattern.EXPERIENCE,
            text=f"Q{i}",
        )
        session.add(q)
        await session.flush()
        questions.append(q)
    for q in questions[:answered]:
        session.add(
            Answer(
                candidate_id=candidate.id, question_id=q.id, transcript="ответ",
                processing_status=AnswerProcessingStatus.READY,
            )
        )
    await session.commit()
    return candidate, questions


@pytest.mark.anyio
async def test_resume_returns_current_question(session: AsyncSession) -> None:
    candidate, questions = await _seed(session, answered=2)
    state = await session_state(session, candidate)

    # Шаг 1: два вопроса отвечены — возвращаемся к третьему
    assert state.current_question is not None
    assert state.current_question.id == questions[2].id
    assert state.answered_count == 2 and state.total == 3
    assert state.finished is False


@pytest.mark.anyio
async def test_interrupt_marks_technically_lost_and_needs_check(session: AsyncSession) -> None:
    candidate, questions = await _seed(session, answered=2)
    current = questions[2]

    answer = await mark_current_technically_lost(session, candidate)

    # Шаг 2: текущий вопрос помечен technically_lost
    assert answer is not None
    assert answer.question_id == current.id
    assert answer.technically_lost is True
    # Р11: топик получает needs_check, а не not_confirmed
    assessment = await session.scalar(
        select(TopicAssessment).where(TopicAssessment.topic_id == current.topic_id)
    )
    assert assessment is not None
    assert assessment.system_status == AssessmentStatus.NEEDS_CHECK
    # сессия завершена (все три вопроса теперь имеют ответ/пометку)
    state = await session_state(session, candidate)
    assert state.finished is True


@pytest.mark.anyio
async def test_expired_link_denies_access(session: AsyncSession) -> None:
    candidate, _ = await _seed(session, answered=1, expires_in_days=-1)

    # Шаг 3: истёкший expires_at — доступа нет
    with pytest.raises(HTTPException) as exc:
        await session_state(session, candidate)
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_finished_when_all_answered(session: AsyncSession) -> None:
    candidate, _ = await _seed(session, answered=3)
    state = await session_state(session, candidate)
    assert state.current_question is None
    assert state.finished is True
