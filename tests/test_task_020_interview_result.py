"""Сборка InterviewResult: агрегация TopicAssessment с фиксацией версий (TASK-020)."""

import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.candidate import Candidate
from app.models.interview_result import InterviewRecommendation, InterviewResult
from app.models.stop_factor import StopFactorFlag
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.topic_assessment import (
    AssessmentConfidence,
    AssessmentStatus,
    TopicAssessment,
)
from app.models.vacancy import Vacancy, VacancyGrade
from app.services.interview_result import assemble_interview_result

M = TopicImportance.MANDATORY
D = TopicImportance.DESIRED


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        yield db
    await engine.dispose()


async def _seed(
    session: AsyncSession,
    matrix: list[tuple[TopicImportance, AssessmentStatus, AssessmentStatus]],
    *,
    version: int = 2,
    stop_triggered: bool = False,
) -> uuid.UUID:
    """matrix: список (importance, system_status, current_status)."""
    vacancy = Vacancy(id=uuid.uuid4(), title="Backend", grade=VacancyGrade.MIDDLE, version=version)
    vacancy.lineage_id = vacancy.id
    candidate = Candidate(vacancy_id=vacancy.id)
    session.add_all([vacancy, candidate])
    await session.flush()

    for i, (importance, system_status, current_status) in enumerate(matrix):
        topic = Topic(
            vacancy_id=vacancy.id,
            title=f"Топик {i}",
            skill_type=SkillType.HARD,
            importance=importance,
            order=i,
        )
        session.add(topic)
        await session.flush()
        session.add(
            TopicAssessment(
                candidate_id=candidate.id,
                topic_id=topic.id,
                system_status=system_status,
                current_status=current_status,
                confidence=AssessmentConfidence.HIGH,
            )
        )

    if stop_triggered:
        session.add(
            StopFactorFlag(
                candidate_id=candidate.id,
                stop_factor="Не готов к переезду",
                triggered=True,
                confidence=AssessmentConfidence.HIGH,
                evidence={"quote": "не готов", "start_sec": 1.0, "end_sec": 2.0},
            )
        )
    await session.commit()
    return candidate.id


def _same(status: AssessmentStatus) -> tuple[AssessmentStatus, AssessmentStatus]:
    return status, status


@pytest.mark.anyio
async def test_assemble_creates_result(session: AsyncSession) -> None:
    candidate_id = await _seed(
        session,
        [
            (M, *_same(AssessmentStatus.CONFIRMED)),
            (M, *_same(AssessmentStatus.CONFIRMED)),
            (M, *_same(AssessmentStatus.NEEDS_CHECK)),
        ],
    )

    result = await assemble_interview_result(session, candidate_id)

    assert result is not None
    assert (result.confirmed_count, result.needs_check_count, result.not_confirmed_count) == (
        2,
        1,
        0,
    )
    assert result.mandatory_coverage is None  # есть спорный
    assert result.recommendation == InterviewRecommendation.ADDITIONAL_CHECK


@pytest.mark.anyio
async def test_version_fields_populated(session: AsyncSession) -> None:
    candidate_id = await _seed(
        session, [(M, *_same(AssessmentStatus.CONFIRMED))], version=3
    )

    result = await assemble_interview_result(
        session, candidate_id, model_version="qwen-test", prompt_version="topic-assessment-v1"
    )

    assert result is not None
    assert result.vacancy_version == 3
    assert result.model_version == "qwen-test"
    assert result.prompt_version == "topic-assessment-v1"


@pytest.mark.anyio
async def test_idempotent_no_duplicate_and_updates(session: AsyncSession) -> None:
    candidate_id = await _seed(session, [(M, *_same(AssessmentStatus.NEEDS_CHECK))])

    first = await assemble_interview_result(session, candidate_id)
    assert first is not None
    assert first.recommendation == InterviewRecommendation.ADDITIONAL_CHECK

    # эксперт закрыл спорный топик в confirmed -> пересборка обновляет ту же запись
    assessment = await session.scalar(
        select(TopicAssessment).where(TopicAssessment.candidate_id == candidate_id)
    )
    assessment.current_status = AssessmentStatus.CONFIRMED
    await session.commit()

    second = await assemble_interview_result(session, candidate_id)
    assert second is not None
    assert second.recommendation == InterviewRecommendation.FIT
    assert second.mandatory_coverage == Decimal("1.0000")

    total = await session.scalar(select(func.count()).select_from(InterviewResult))
    assert total == 1


@pytest.mark.anyio
async def test_all_confirmed_fit_with_full_coverage(session: AsyncSession) -> None:
    candidate_id = await _seed(
        session,
        [(M, *_same(AssessmentStatus.CONFIRMED)), (M, *_same(AssessmentStatus.CONFIRMED))],
    )

    result = await assemble_interview_result(session, candidate_id)

    assert result is not None
    assert result.recommendation == InterviewRecommendation.FIT
    assert result.mandatory_coverage == Decimal("1.0000")


@pytest.mark.anyio
async def test_triggered_stop_factor_forces_not_fit(session: AsyncSession) -> None:
    candidate_id = await _seed(
        session,
        [(M, *_same(AssessmentStatus.CONFIRMED))],
        stop_triggered=True,
    )

    result = await assemble_interview_result(session, candidate_id)

    assert result is not None
    assert result.recommendation == InterviewRecommendation.NOT_FIT


@pytest.mark.anyio
async def test_aggregation_uses_current_status(session: AsyncSession) -> None:
    # system_status=needs_check, но эксперт выставил current_status=confirmed
    candidate_id = await _seed(
        session,
        [(M, AssessmentStatus.NEEDS_CHECK, AssessmentStatus.CONFIRMED)],
    )

    result = await assemble_interview_result(session, candidate_id)

    assert result is not None
    assert result.recommendation == InterviewRecommendation.FIT
    assert result.mandatory_coverage == Decimal("1.0000")


@pytest.mark.anyio
async def test_missing_candidate_returns_none(session: AsyncSession) -> None:
    result = await assemble_interview_result(session, uuid.uuid4())
    assert result is None
