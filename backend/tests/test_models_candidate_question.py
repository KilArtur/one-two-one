"""Tests for Candidate / InterviewLink / Question ORM models (TASK-005)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    Candidate,
    CandidateStatus,
    Importance,
    InterviewLink,
    Question,
    QuestionPattern,
    QuestionType,
    SkillType,
    Topic,
    Vacancy,
    VacancyGrade,
    VacancyStatus,
)


async def _seed_vacancy_topic(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    vacancy_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    session.add(
        Vacancy(
            id=vacancy_id,
            title="Backend Engineer",
            grade=VacancyGrade.MIDDLE,
            tasks="Build APIs",
            specialist_profile="Python",
            version=1,
            status=VacancyStatus.ACTIVE,
        )
    )
    session.add(
        Topic(
            id=topic_id,
            vacancy_id=vacancy_id,
            title="Kafka",
            skill_type=SkillType.HARD,
            importance=Importance.MANDATORY,
            requirement_description="Kafka ops",
            depth_expectations="Partitions",
            order=1,
        )
    )
    await session.flush()
    return vacancy_id, topic_id


@pytest.mark.asyncio
async def test_candidate_question_tables_exist() -> None:
    """Tables candidate, interview_link, question are present after migration."""
    get_settings.cache_clear()
    from app.db import engine

    async with engine.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )
    assert "candidate" in table_names
    assert "interview_link" in table_names
    assert "question" in table_names


@pytest.mark.asyncio
async def test_candidate_question_columns() -> None:
    """PRD §5 columns exist on candidate, interview_link, and question."""
    get_settings.cache_clear()
    from app.db import engine

    async with engine.connect() as conn:

        def _columns(sync_conn: object, table: str) -> set[str]:
            return {col["name"] for col in inspect(sync_conn).get_columns(table)}

        candidate_cols = await conn.run_sync(lambda c: _columns(c, "candidate"))
        link_cols = await conn.run_sync(lambda c: _columns(c, "interview_link"))
        question_cols = await conn.run_sync(lambda c: _columns(c, "question"))

    assert candidate_cols == {
        "id",
        "vacancy_id",
        "resume_text",
        "resume_file_url",
        "consent_given_at",
        "status",
    }
    assert link_cols == {
        "id",
        "candidate_id",
        "token",
        "expires_at",
        "used_at",
        "revoked",
    }
    assert question_cols == {
        "id",
        "topic_id",
        "type",
        "pattern",
        "text",
        "source_reason",
        "reviewed_by_expert",
        "parent_question_id",
    }


@pytest.mark.asyncio
async def test_insert_candidate_and_core_question() -> None:
    """ORM insert of candidate + core question with FKs."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    candidate_id = uuid.uuid4()
    question_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        vacancy_id, topic_id = await _seed_vacancy_topic(session)
        session.add(
            Candidate(
                id=candidate_id,
                vacancy_id=vacancy_id,
                resume_text="Python developer",
                status=CandidateStatus.INVITED,
            )
        )
        session.add(
            Question(
                id=question_id,
                topic_id=topic_id,
                type=QuestionType.CORE,
                pattern=QuestionPattern.TECHNICAL,
                text="How do you operate Kafka in production?",
                source_reason="Checks production Kafka experience",
            )
        )
        await session.commit()

        candidate = await session.get(Candidate, candidate_id)
        assert candidate is not None
        assert candidate.status == CandidateStatus.INVITED

        question = await session.get(Question, question_id)
        assert question is not None
        assert question.type == QuestionType.CORE
        assert question.pattern == QuestionPattern.TECHNICAL
        assert question.parent_question_id is None

        await session.delete(question)
        await session.delete(candidate)
        topic = await session.get(Topic, topic_id)
        vacancy = await session.get(Vacancy, vacancy_id)
        assert topic is not None and vacancy is not None
        await session.delete(topic)
        await session.delete(vacancy)
        await session.commit()


@pytest.mark.asyncio
async def test_follow_up_question_self_fk() -> None:
    """follow_up question references parent via parent_question_id."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    core_id = uuid.uuid4()
    follow_up_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        vacancy_id, topic_id = await _seed_vacancy_topic(session)
        session.add(
            Question(
                id=core_id,
                topic_id=topic_id,
                type=QuestionType.CORE,
                pattern=QuestionPattern.EXPERIENCE,
                text="Describe a Kafka outage you handled.",
                source_reason="Experience signal",
            )
        )
        session.add(
            Question(
                id=follow_up_id,
                topic_id=topic_id,
                type=QuestionType.FOLLOW_UP,
                pattern=QuestionPattern.REASONING,
                text="What would you change next time?",
                source_reason="Deepens reasoning",
                parent_question_id=core_id,
            )
        )
        await session.commit()

        follow_up = await session.get(Question, follow_up_id)
        assert follow_up is not None
        assert follow_up.type == QuestionType.FOLLOW_UP
        assert follow_up.parent_question_id == core_id

        result = await session.execute(
            select(Question).where(Question.parent_question_id == core_id)
        )
        children = list(result.scalars())
        assert len(children) == 1
        assert children[0].id == follow_up_id

        await session.execute(
            text("DELETE FROM question WHERE id = :id"),
            {"id": follow_up_id},
        )
        await session.execute(
            text("DELETE FROM question WHERE id = :id"),
            {"id": core_id},
        )
        await session.execute(
            text("DELETE FROM topic WHERE id = :id"),
            {"id": topic_id},
        )
        await session.execute(
            text("DELETE FROM vacancy WHERE id = :id"),
            {"id": vacancy_id},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_interview_link_for_candidate() -> None:
    """InterviewLink attaches to candidate with unique token and defaults."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    candidate_id = uuid.uuid4()
    link_id = uuid.uuid4()
    token = f"tok-{uuid.uuid4().hex}"
    expires = datetime.now(UTC) + timedelta(days=7)

    async with AsyncSessionLocal() as session:
        vacancy_id, topic_id = await _seed_vacancy_topic(session)
        session.add(
            Candidate(
                id=candidate_id,
                vacancy_id=vacancy_id,
                resume_text="",
                status=CandidateStatus.INVITED,
            )
        )
        session.add(
            InterviewLink(
                id=link_id,
                candidate_id=candidate_id,
                token=token,
                expires_at=expires,
            )
        )
        await session.commit()

        link = await session.get(InterviewLink, link_id)
        assert link is not None
        assert link.token == token
        assert link.revoked is False
        assert link.used_at is None

        await session.delete(link)
        candidate = await session.get(Candidate, candidate_id)
        assert candidate is not None
        await session.delete(candidate)
        topic = await session.get(Topic, topic_id)
        vacancy = await session.get(Vacancy, vacancy_id)
        assert topic is not None and vacancy is not None
        await session.delete(topic)
        await session.delete(vacancy)
        await session.commit()
