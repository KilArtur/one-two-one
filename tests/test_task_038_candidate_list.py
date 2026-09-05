"""Список кандидатов вакансии: статус обработки, тройка чисел, фильтр (TASK-038)."""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.answer import Answer, AnswerProcessingStatus
from app.models.candidate import Candidate
from app.models.interview_result import InterviewRecommendation, InterviewResult
from app.models.question import Question, QuestionPattern, QuestionType
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.vacancy import Vacancy, VacancyGrade
from app.services.candidate_overview import list_vacancy_candidates


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


async def _seed(session: AsyncSession) -> uuid.UUID:
    vacancy = Vacancy(id=uuid.uuid4(), title="Backend", grade=VacancyGrade.MIDDLE)
    vacancy.lineage_id = vacancy.id
    topic = Topic(
        vacancy_id=vacancy.id,
        title="PostgreSQL",
        skill_type=SkillType.HARD,
        importance=TopicImportance.MANDATORY,
        order=0,
    )
    vacancy.topics = [topic]
    session.add(vacancy)
    await session.flush()
    question = Question(
        topic_id=topic.id, type=QuestionType.CORE, pattern=QuestionPattern.EXPERIENCE, text="Q"
    )
    session.add(question)
    await session.flush()

    # ready-кандидат с результатом (тройка чисел)
    ready = Candidate(vacancy_id=vacancy.id)
    session.add(ready)
    await session.flush()
    session.add(
        Answer(
            candidate_id=ready.id,
            question_id=question.id,
            processing_status=AnswerProcessingStatus.READY,
        )
    )
    session.add(
        InterviewResult(
            candidate_id=ready.id,
            recommendation=InterviewRecommendation.FIT,
            confirmed_count=3,
            needs_check_count=1,
            not_confirmed_count=0,
            vacancy_version=1,
            model_version="m",
            prompt_version="p",
        )
    )
    # error-кандидат
    errored = Candidate(vacancy_id=vacancy.id)
    session.add(errored)
    await session.flush()
    session.add(
        Answer(
            candidate_id=errored.id,
            question_id=question.id,
            processing_status=AnswerProcessingStatus.ERROR,
        )
    )
    # кандидат без ответов
    fresh = Candidate(vacancy_id=vacancy.id)
    session.add(fresh)
    await session.commit()
    return vacancy.id


@pytest.mark.anyio
async def test_list_shows_candidates_with_status_and_triple(session: AsyncSession) -> None:
    vacancy_id = await _seed(session)
    overviews = await list_vacancy_candidates(session, vacancy_id)

    assert len(overviews) == 3
    by_status = {o.processing_status for o in overviews}
    assert {"ready", "error", "not_started"} <= by_status
    ready = next(o for o in overviews if o.processing_status == "ready")
    assert (ready.confirmed_count, ready.needs_check_count, ready.not_confirmed_count) == (3, 1, 0)
    assert ready.recommendation == "fit"
    assert ready.skill_coverage == 0.75
    assert ready.mandatory_coverage is None


@pytest.mark.anyio
async def test_error_candidate_flagged(session: AsyncSession) -> None:
    vacancy_id = await _seed(session)
    overviews = await list_vacancy_candidates(session, vacancy_id)
    assert any(o.processing_status == "error" for o in overviews)


@pytest.mark.anyio
async def test_filter_by_processing_status(session: AsyncSession) -> None:
    vacancy_id = await _seed(session)
    only_error = await list_vacancy_candidates(session, vacancy_id, processing_status="error")
    assert len(only_error) == 1
    assert only_error[0].processing_status == "error"
