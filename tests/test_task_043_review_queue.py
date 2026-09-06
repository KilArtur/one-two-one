"""Очередь ревью по ролям (M7, принцип 5): фильтр по роли, сортировка, закрытие (TASK-043)."""

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.candidate import Candidate
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.topic_assessment import (
    AssessmentConfidence,
    AssessmentStatus,
    TopicAssessment,
)
from app.models.vacancy import Vacancy, VacancyGrade
from app.services.auth import AppRole, CurrentUser
from app.services.review_queue import review_queue


def _user(role: AppRole) -> CurrentUser:
    return CurrentUser(username=f"{role.value}", role=role)


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


async def _seed(session: AsyncSession) -> dict:
    vacancy = Vacancy(id=uuid.uuid4(), title="Backend", grade=VacancyGrade.MIDDLE)
    vacancy.lineage_id = vacancy.id
    candidate = Candidate(vacancy_id=vacancy.id)
    session.add_all([vacancy, candidate])
    await session.flush()
    ids: dict = {}

    def add_topic(title, skill, status, confidence):
        topic = Topic(
            vacancy_id=vacancy.id,
            title=title,
            skill_type=skill,
            importance=TopicImportance.MANDATORY,
            order=0,
        )
        session.add(topic)
        return topic

    specs = [
        ("hard-low", SkillType.HARD, AssessmentStatus.NEEDS_CHECK, AssessmentConfidence.LOW),
        ("hard-med", SkillType.HARD, AssessmentStatus.NEEDS_CHECK, AssessmentConfidence.MEDIUM),
        ("hard-high", SkillType.HARD, AssessmentStatus.NEEDS_CHECK, AssessmentConfidence.HIGH),
        ("hard-confirmed", SkillType.HARD, AssessmentStatus.CONFIRMED, AssessmentConfidence.LOW),
        ("soft-low", SkillType.SOFT, AssessmentStatus.NEEDS_CHECK, AssessmentConfidence.LOW),
    ]
    for title, skill, status_, conf in specs:
        topic = add_topic(title, skill, status_, conf)
        await session.flush()
        assessment = TopicAssessment(
            candidate_id=candidate.id,
            topic_id=topic.id,
            system_status=status_,
            current_status=status_,
            confidence=conf,
        )
        session.add(assessment)
        await session.flush()
        ids[title] = assessment.id
    await session.commit()
    return ids


@pytest.mark.anyio
async def test_tech_sees_only_hard_needs_check(session: AsyncSession) -> None:
    await _seed(session)
    items = await review_queue(session, _user(AppRole.TECH_SPECIALIST))

    titles = {item["topic_title"] for item in items}
    assert titles == {"hard-low", "hard-med", "hard-high"}  # не soft и не confirmed


@pytest.mark.anyio
async def test_sorted_by_confidence_low_first(session: AsyncSession) -> None:
    await _seed(session)
    items = await review_queue(session, _user(AppRole.TECH_SPECIALIST))

    order = [item["confidence"] for item in items]
    assert order == [
        AssessmentConfidence.LOW,
        AssessmentConfidence.MEDIUM,
        AssessmentConfidence.HIGH,
    ]


@pytest.mark.anyio
async def test_closed_topic_leaves_queue(session: AsyncSession) -> None:
    ids = await _seed(session)
    assessment = await session.get(TopicAssessment, ids["hard-low"])
    assessment.current_status = AssessmentStatus.CONFIRMED
    await session.commit()

    items = await review_queue(session, _user(AppRole.TECH_SPECIALIST))
    titles = {item["topic_title"] for item in items}
    assert "hard-low" not in titles
    assert titles == {"hard-med", "hard-high"}


@pytest.mark.anyio
async def test_reviewed_needs_check_leaves_queue(session: AsyncSession) -> None:
    """Эксперт сохранил статус без смены — топик уходит из очереди."""
    ids = await _seed(session)
    assessment = await session.get(TopicAssessment, ids["hard-low"])
    assert assessment is not None
    assessment.reviewed_by = uuid.uuid4()
    assessment.current_status = AssessmentStatus.NEEDS_CHECK
    await session.commit()

    items = await review_queue(session, _user(AppRole.TECH_SPECIALIST))
    titles = {item["topic_title"] for item in items}
    assert "hard-low" not in titles
    assert titles == {"hard-med", "hard-high"}


@pytest.mark.anyio
async def test_hiring_manager_sees_only_soft(session: AsyncSession) -> None:
    await _seed(session)
    items = await review_queue(session, _user(AppRole.HIRING_MANAGER))
    assert {item["topic_title"] for item in items} == {"soft-low"}


@pytest.mark.anyio
async def test_recruiter_has_no_queue(session: AsyncSession) -> None:
    await _seed(session)
    with pytest.raises(HTTPException) as exc:
        await review_queue(session, _user(AppRole.RECRUITER))
    assert exc.value.status_code == 403
