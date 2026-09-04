"""Tests for Vacancy / Topic ORM models (TASK-004)."""

import uuid

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    Importance,
    SkillType,
    Topic,
    Vacancy,
    VacancyGrade,
    VacancyStatus,
)


@pytest.mark.asyncio
async def test_vacancy_topic_tables_exist() -> None:
    """Tables vacancy and topic are present after migration."""
    get_settings.cache_clear()
    from app.db import engine

    async with engine.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )
    assert "vacancy" in table_names
    assert "topic" in table_names


@pytest.mark.asyncio
async def test_vacancy_and_topic_columns() -> None:
    """PRD §5 columns exist on vacancy and topic."""
    get_settings.cache_clear()
    from app.db import engine

    async with engine.connect() as conn:

        def _columns(sync_conn: object, table: str) -> set[str]:
            return {col["name"] for col in inspect(sync_conn).get_columns(table)}

        vacancy_cols = await conn.run_sync(lambda c: _columns(c, "vacancy"))
        topic_cols = await conn.run_sync(lambda c: _columns(c, "topic"))

    assert vacancy_cols == {
        "id",
        "title",
        "grade",
        "tasks",
        "stop_factors",
        "specialist_profile",
        "version",
        "status",
    }
    assert topic_cols == {
        "id",
        "vacancy_id",
        "title",
        "skill_type",
        "importance",
        "requirement_description",
        "depth_expectations",
        "verifiable_by_interview",
        "order",
    }


@pytest.mark.asyncio
async def test_insert_vacancy_with_topic() -> None:
    """ORM insert of vacancy + related topic with FK."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    vacancy_id = uuid.uuid4()
    topic_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        vacancy = Vacancy(
            id=vacancy_id,
            title="Backend Engineer",
            grade=VacancyGrade.MIDDLE_PLUS,
            tasks="Build APIs",
            stop_factors=["no production experience"],
            specialist_profile="Python / FastAPI",
            version=1,
            status=VacancyStatus.ACTIVE,
        )
        topic = Topic(
            id=topic_id,
            vacancy_id=vacancy_id,
            title="Kafka in production",
            skill_type=SkillType.HARD,
            importance=Importance.MANDATORY,
            requirement_description="Hands-on Kafka ops",
            depth_expectations="Can describe partitions and consumer groups",
            order=1,
        )
        session.add(vacancy)
        session.add(topic)
        await session.commit()

        loaded = await session.get(Vacancy, vacancy_id)
        assert loaded is not None
        assert loaded.grade == VacancyGrade.MIDDLE_PLUS
        assert loaded.stop_factors == ["no production experience"]

        result = await session.execute(
            select(Topic).where(Topic.vacancy_id == vacancy_id)
        )
        topics = list(result.scalars())
        assert len(topics) == 1
        assert topics[0].verifiable_by_interview is True
        assert topics[0].skill_type == SkillType.HARD

        await session.delete(topics[0])
        await session.delete(loaded)
        await session.commit()


@pytest.mark.asyncio
async def test_verifiable_by_interview_default_true() -> None:
    """DB default for verifiable_by_interview is true when omitted."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    vacancy_id = uuid.uuid4()
    topic_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        assert isinstance(session, AsyncSession)
        await session.execute(
            text(
                """
                INSERT INTO vacancy (
                    id, title, grade, tasks, stop_factors,
                    specialist_profile, version, status
                ) VALUES (
                    :id, 'T', 'junior', '', '{}', '', 1, 'draft'
                )
                """
            ),
            {"id": vacancy_id},
        )
        await session.execute(
            text(
                """
                INSERT INTO topic (
                    id, vacancy_id, title, skill_type, importance,
                    requirement_description, depth_expectations, "order"
                ) VALUES (
                    :id, :vacancy_id, 'Soft skills', 'soft', 'desired',
                    '', '', 0
                )
                """
            ),
            {"id": topic_id, "vacancy_id": vacancy_id},
        )
        await session.commit()

        topic = await session.get(Topic, topic_id)
        assert topic is not None
        assert topic.verifiable_by_interview is True

        await session.execute(
            text("DELETE FROM topic WHERE id = :id"),
            {"id": topic_id},
        )
        await session.execute(
            text("DELETE FROM vacancy WHERE id = :id"),
            {"id": vacancy_id},
        )
        await session.commit()
