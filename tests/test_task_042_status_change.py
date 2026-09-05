"""Смена статуса экспертом (Р21): обязательный комментарий, append-only, system_status."""

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.topic_assessments import change_status
from app.db import Base
from app.models.candidate import Candidate
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.topic_assessment import (
    AssessmentConfidence,
    AssessmentStatus,
    StatusChangeLog,
    TopicAssessment,
)
from app.models.vacancy import Vacancy, VacancyGrade
from app.schemas.assessment import TopicStatusChangeRequest
from app.services.auth import AppRole, CurrentUser
from app.services.topic_assessment import change_candidate_topic_status, change_topic_status


def _user(role: AppRole) -> CurrentUser:
    return CurrentUser(username=f"{role.value}-user", role=role)


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


async def _seed(session: AsyncSession, skill: SkillType = SkillType.HARD) -> uuid.UUID:
    vacancy = Vacancy(id=uuid.uuid4(), title="Backend", grade=VacancyGrade.MIDDLE)
    vacancy.lineage_id = vacancy.id
    topic = Topic(
        vacancy_id=vacancy.id,
        title="PostgreSQL",
        skill_type=skill,
        importance=TopicImportance.MANDATORY,
        order=0,
    )
    vacancy.topics = [topic]
    candidate = Candidate(vacancy_id=vacancy.id)
    session.add_all([vacancy, candidate])
    await session.flush()
    assessment = TopicAssessment(
        candidate_id=candidate.id,
        topic_id=topic.id,
        system_status=AssessmentStatus.NEEDS_CHECK,
        current_status=AssessmentStatus.NEEDS_CHECK,
        confidence=AssessmentConfidence.LOW,
    )
    session.add(assessment)
    await session.commit()
    return assessment.id


def test_comment_is_mandatory() -> None:
    # Шаг 1: пустой комментарий недопустим (валидация -> 422 на уровне API)
    with pytest.raises(ValidationError):
        TopicStatusChangeRequest(new_status=AssessmentStatus.CONFIRMED, comment="")


@pytest.mark.anyio
async def test_system_status_preserved_current_updated(session: AsyncSession) -> None:
    assessment_id = await _seed(session, SkillType.HARD)

    updated = await change_topic_status(
        session,
        assessment_id,
        user=_user(AppRole.TECH_SPECIALIST),
        new_status=AssessmentStatus.CONFIRMED,
        comment="Проверил hard-топик вручную",
    )

    # Шаг 2: system_status прежний, current_status новый
    assert updated.system_status == AssessmentStatus.NEEDS_CHECK
    assert updated.current_status == AssessmentStatus.CONFIRMED


@pytest.mark.anyio
async def test_two_changes_append_two_log_entries(session: AsyncSession) -> None:
    assessment_id = await _seed(session, SkillType.HARD)
    user = _user(AppRole.TECH_SPECIALIST)

    await change_topic_status(
        session, assessment_id, user=user, new_status=AssessmentStatus.CONFIRMED, comment="раз"
    )
    await change_topic_status(
        session, assessment_id, user=user, new_status=AssessmentStatus.NOT_CONFIRMED, comment="два"
    )

    # Шаг 3: две смены — две append-only записи
    total = await session.scalar(
        select(func.count())
        .select_from(StatusChangeLog)
        .where(StatusChangeLog.assessment_id == assessment_id)
    )
    assert total == 2
    logs = list(
        await session.scalars(
            select(StatusChangeLog)
            .where(StatusChangeLog.assessment_id == assessment_id)
            .order_by(StatusChangeLog.created_at)
        )
    )
    assert logs[0].old_status == AssessmentStatus.NEEDS_CHECK
    assert logs[0].new_status == AssessmentStatus.CONFIRMED
    assert logs[1].old_status == AssessmentStatus.CONFIRMED
    assert logs[1].new_status == AssessmentStatus.NOT_CONFIRMED
    # system_status по-прежнему не тронут
    assessment = await session.get(TopicAssessment, assessment_id)
    assert assessment.system_status == AssessmentStatus.NEEDS_CHECK


@pytest.mark.anyio
async def test_recruiter_forbidden(session: AsyncSession) -> None:
    assessment_id = await _seed(session, SkillType.HARD)
    with pytest.raises(HTTPException) as exc:
        await change_topic_status(
            session,
            assessment_id,
            user=_user(AppRole.RECRUITER),
            new_status=AssessmentStatus.CONFIRMED,
            comment="нельзя",
        )
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_hard_soft_rbac(session: AsyncSession) -> None:
    hard_id = await _seed(session, SkillType.HARD)
    soft_id = await _seed(session, SkillType.SOFT)

    with pytest.raises(HTTPException) as exc:
        await change_topic_status(
            session,
            hard_id,
            user=_user(AppRole.HIRING_MANAGER),
            new_status=AssessmentStatus.CONFIRMED,
            comment="x",
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        await change_topic_status(
            session,
            soft_id,
            user=_user(AppRole.TECH_SPECIALIST),
            new_status=AssessmentStatus.CONFIRMED,
            comment="x",
        )
    assert exc.value.status_code == 403

    # НМ может менять soft
    updated = await change_topic_status(
        session,
        soft_id,
        user=_user(AppRole.HIRING_MANAGER),
        new_status=AssessmentStatus.CONFIRMED,
        comment="ок",
    )
    assert updated.current_status == AssessmentStatus.CONFIRMED


@pytest.mark.anyio
async def test_out_of_scope_rejected_by_endpoint(session: AsyncSession) -> None:
    assessment_id = await _seed(session, SkillType.HARD)
    with pytest.raises(HTTPException) as exc:
        await change_status(
            assessment_id,
            TopicStatusChangeRequest(new_status=AssessmentStatus.OUT_OF_SCOPE, comment="x"),
            _user(AppRole.TECH_SPECIALIST),
            session,
        )
    assert exc.value.status_code == 422


@pytest.mark.anyio
async def test_missing_assessment_returns_none(session: AsyncSession) -> None:
    result = await change_topic_status(
        session,
        uuid.uuid4(),
        user=_user(AppRole.TECH_SPECIALIST),
        new_status=AssessmentStatus.CONFIRMED,
        comment="x",
    )
    assert result is None


@pytest.mark.anyio
async def test_card_status_creates_assessment_if_missing(session: AsyncSession) -> None:
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
    candidate = Candidate(vacancy_id=vacancy.id)
    session.add_all([vacancy, candidate])
    await session.commit()

    updated = await change_candidate_topic_status(
        session,
        candidate.id,
        topic.id,
        user=_user(AppRole.TECH_SPECIALIST),
        new_status=AssessmentStatus.CONFIRMED,
        comment="Проверил по видео",
    )

    assert updated is not None
    assert updated.system_status == AssessmentStatus.NEEDS_CHECK
    assert updated.current_status == AssessmentStatus.CONFIRMED
