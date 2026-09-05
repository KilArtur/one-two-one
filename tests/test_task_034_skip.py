"""Пропуск вопроса (Р10): Answer.skipped=true (TASK-034)."""

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.candidate_interview import skip_question
from app.db import Base
from app.models.answer import Answer
from app.models.candidate import Candidate
from app.models.question import Question, QuestionPattern, QuestionType
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.vacancy import Vacancy, VacancyGrade


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


async def _seed(session: AsyncSession) -> tuple[Candidate, uuid.UUID]:
    vacancy = Vacancy(id=uuid.uuid4(), title="Backend", grade=VacancyGrade.MIDDLE)
    vacancy.lineage_id = vacancy.id
    topic = Topic(
        vacancy_id=vacancy.id, title="PostgreSQL", skill_type=SkillType.HARD,
        importance=TopicImportance.MANDATORY, order=0,
    )
    vacancy.topics = [topic]
    candidate = Candidate(vacancy_id=vacancy.id)
    session.add_all([vacancy, candidate])
    await session.flush()
    question = Question(
        topic_id=topic.id, type=QuestionType.CORE, pattern=QuestionPattern.EXPERIENCE, text="Q"
    )
    session.add(question)
    await session.commit()
    return candidate, question.id


@pytest.mark.anyio
async def test_skip_sets_skipped_true(session: AsyncSession) -> None:
    candidate, question_id = await _seed(session)
    result = await skip_question(question_id, candidate, session)

    assert result.skipped is True
    answer = await session.scalar(
        select(Answer).where(Answer.candidate_id == candidate.id, Answer.question_id == question_id)
    )
    assert answer is not None and answer.skipped is True


@pytest.mark.anyio
async def test_skip_twice_conflicts(session: AsyncSession) -> None:
    candidate, question_id = await _seed(session)
    await skip_question(question_id, candidate, session)
    with pytest.raises(HTTPException) as exc:
        await skip_question(question_id, candidate, session)
    assert exc.value.status_code == 409


@pytest.mark.anyio
async def test_skip_foreign_question_404(session: AsyncSession) -> None:
    candidate, _ = await _seed(session)
    with pytest.raises(HTTPException) as exc:
        await skip_question(uuid.uuid4(), candidate, session)
    assert exc.value.status_code == 404
