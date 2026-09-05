"""Карточка результата (M7, принцип 1): матрица, рекомендация Р5, слои (TASK-039)."""

import dataclasses
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.candidate import Candidate
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.topic_assessment import (
    AssessmentConfidence,
    AssessmentStatus,
    ReviewerRole,
    StatusChangeLog,
    TopicAssessment,
)
from app.models.vacancy import Vacancy, VacancyGrade
from app.services.result_card import ResultCard, build_result_card


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
    candidate = Candidate(vacancy_id=vacancy.id, resume_text="10 лет Python")
    session.add_all([vacancy, candidate])
    await session.flush()

    specs = [
        ("PostgreSQL", SkillType.HARD, TopicImportance.MANDATORY, AssessmentStatus.CONFIRMED,
         AssessmentStatus.CONFIRMED, False),
        ("Kafka", SkillType.HARD, TopicImportance.MANDATORY, AssessmentStatus.NEEDS_CHECK,
         AssessmentStatus.CONFIRMED, True),  # правлено экспертом
    ]
    for i, (title, skill, imp, sys_s, cur_s, edited) in enumerate(specs):
        topic = Topic(
            vacancy_id=vacancy.id, title=title, skill_type=skill, importance=imp, order=i
        )
        session.add(topic)
        await session.flush()
        assessment = TopicAssessment(
            candidate_id=candidate.id, topic_id=topic.id,
            system_status=sys_s, current_status=cur_s, confidence=AssessmentConfidence.HIGH,
        )
        session.add(assessment)
        await session.flush()
        if edited:
            session.add(
                StatusChangeLog(
                    assessment_id=assessment.id, author_id=uuid.uuid4(),
                    author_role=ReviewerRole.TECH_SPECIALIST, old_status=sys_s, new_status=cur_s,
                    comment="проверил",
                )
            )
    await session.commit()
    return candidate.id


@pytest.mark.anyio
async def test_matrix_and_recommendation(session: AsyncSession) -> None:
    candidate_id = await _seed(session)
    card = await build_result_card(session, candidate_id)

    assert card is not None
    # матрица первым объектом, в порядке order
    assert [t.topic_title for t in card.topics] == ["PostgreSQL", "Kafka"]
    # оба обязательных теперь confirmed -> fit
    assert card.recommendation == "fit"
    assert card.recommendation_reason == "all_mandatory_confirmed"
    assert (card.confirmed_count, card.needs_check_count, card.not_confirmed_count) == (2, 0, 0)
    assert card.resume_text == "10 лет Python"


@pytest.mark.anyio
async def test_author_reflects_expert_edit(session: AsyncSession) -> None:
    candidate_id = await _seed(session)
    card = await build_result_card(session, candidate_id)

    by_title = {t.topic_title: t for t in card.topics}
    # системный статус сохранён отдельно от текущего у правленого топика
    assert by_title["Kafka"].system_status == "needs_check"
    assert by_title["Kafka"].current_status == "confirmed"
    assert by_title["Kafka"].author == "technical_specialist"
    assert by_title["PostgreSQL"].author == "system"


@pytest.mark.anyio
async def test_no_aggregate_score_field(session: AsyncSession) -> None:
    field_names = {f.name for f in dataclasses.fields(ResultCard)}
    assert not any("score" in name for name in field_names)


@pytest.mark.anyio
async def test_missing_candidate_returns_none(session: AsyncSession) -> None:
    assert await build_result_card(session, uuid.uuid4()) is None
