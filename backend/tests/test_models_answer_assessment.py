"""Tests for Answer / TopicAssessment / StatusChangeLog / InterviewResult (TASK-006)."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    Answer,
    AuthorRole,
    Candidate,
    CandidateStatus,
    Confidence,
    Importance,
    InterviewResult,
    ProcessingStatus,
    Question,
    QuestionPattern,
    QuestionType,
    Recommendation,
    SkillType,
    StatusChangeLog,
    Topic,
    TopicAssessment,
    TopicStatus,
    Vacancy,
    VacancyGrade,
    VacancyStatus,
)


async def _seed_graph(
    session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    vacancy_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    question_id = uuid.uuid4()
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
    session.add(
        Candidate(
            id=candidate_id,
            vacancy_id=vacancy_id,
            resume_text="Python developer",
            status=CandidateStatus.SUBMITTED,
        )
    )
    session.add(
        Question(
            id=question_id,
            topic_id=topic_id,
            type=QuestionType.CORE,
            pattern=QuestionPattern.TECHNICAL,
            text="How do you operate Kafka?",
            source_reason="Production experience",
        )
    )
    await session.flush()
    return vacancy_id, topic_id, candidate_id, question_id


async def _cleanup_graph(
    session: AsyncSession,
    *,
    vacancy_id: uuid.UUID,
    topic_id: uuid.UUID,
    candidate_id: uuid.UUID,
    question_id: uuid.UUID,
) -> None:
    await session.execute(
        text("DELETE FROM interview_result WHERE candidate_id = :id"),
        {"id": candidate_id},
    )
    await session.execute(
        text(
            "DELETE FROM status_change_log WHERE assessment_id IN "
            "(SELECT id FROM topic_assessment WHERE candidate_id = :id)"
        ),
        {"id": candidate_id},
    )
    await session.execute(
        text("DELETE FROM topic_assessment WHERE candidate_id = :id"),
        {"id": candidate_id},
    )
    await session.execute(
        text("DELETE FROM answer WHERE question_id = :id"),
        {"id": question_id},
    )
    await session.execute(
        text("DELETE FROM question WHERE id = :id"),
        {"id": question_id},
    )
    await session.execute(
        text("DELETE FROM candidate WHERE id = :id"),
        {"id": candidate_id},
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
async def test_answer_assessment_tables_exist() -> None:
    """New tables from TASK-006 are present after migration."""
    get_settings.cache_clear()
    from app.db import engine

    async with engine.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )
    assert "answer" in table_names
    assert "topic_assessment" in table_names
    assert "status_change_log" in table_names
    assert "interview_result" in table_names


@pytest.mark.asyncio
async def test_topic_assessment_has_both_statuses() -> None:
    """topic_assessment has system_status and current_status (Р21)."""
    get_settings.cache_clear()
    from app.db import engine

    async with engine.connect() as conn:

        def _columns(sync_conn: object, table: str) -> set[str]:
            return {col["name"] for col in inspect(sync_conn).get_columns(table)}

        cols = await conn.run_sync(lambda c: _columns(c, "topic_assessment"))

    assert "system_status" in cols
    assert "current_status" in cols
    assert "signals" in cols
    assert "evidence" in cols


@pytest.mark.asyncio
async def test_answer_jsonb_and_processing_status() -> None:
    """Answer stores transcript_segments jsonb and processing_status."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    answer_id = uuid.uuid4()
    segments = [
        {"start": 1.0, "end": 3.5, "text": "I ran Kafka in production"},
    ]

    async with AsyncSessionLocal() as session:
        vacancy_id, topic_id, candidate_id, question_id = await _seed_graph(session)
        session.add(
            Answer(
                id=answer_id,
                question_id=question_id,
                transcript="I ran Kafka in production",
                transcript_segments=segments,
                duration_sec=12,
                processing_status=ProcessingStatus.READY,
            )
        )
        await session.commit()

        answer = await session.get(Answer, answer_id)
        assert answer is not None
        assert answer.transcript_segments == segments
        assert answer.processing_status == ProcessingStatus.READY
        assert answer.skipped is False

        await _cleanup_graph(
            session,
            vacancy_id=vacancy_id,
            topic_id=topic_id,
            candidate_id=candidate_id,
            question_id=question_id,
        )


@pytest.mark.asyncio
async def test_insert_assessment_with_evidence_jsonb() -> None:
    """Insert TopicAssessment with evidence jsonb; both statuses set."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    assessment_id = uuid.uuid4()
    question_id_for_evidence = uuid.uuid4()
    evidence = [
        {
            "quote": "I ran Kafka in production",
            "timecode_sec": 1.0,
            "question_id": str(question_id_for_evidence),
        }
    ]
    signals = {
        "correctness": True,
        "example": True,
        "personal_contribution": True,
    }

    async with AsyncSessionLocal() as session:
        vacancy_id, topic_id, candidate_id, question_id = await _seed_graph(session)
        session.add(
            TopicAssessment(
                id=assessment_id,
                candidate_id=candidate_id,
                topic_id=topic_id,
                system_status=TopicStatus.NEEDS_CHECK,
                current_status=TopicStatus.CONFIRMED,
                confidence=Confidence.HIGH,
                signals=signals,
                evidence=evidence,
                reasoning_summary="Expert confirmed after review",
            )
        )
        await session.commit()

        assessment = await session.get(TopicAssessment, assessment_id)
        assert assessment is not None
        assert assessment.system_status == TopicStatus.NEEDS_CHECK
        assert assessment.current_status == TopicStatus.CONFIRMED
        assert assessment.evidence == evidence
        assert assessment.signals == signals

        cols = await session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'topic_assessment' "
                "AND column_name IN ('system_status', 'current_status')"
            )
        )
        status_cols = {row[0] for row in cols}
        assert status_cols == {"system_status", "current_status"}

        await _cleanup_graph(
            session,
            vacancy_id=vacancy_id,
            topic_id=topic_id,
            candidate_id=candidate_id,
            question_id=question_id,
        )


@pytest.mark.asyncio
async def test_status_change_log_append_only() -> None:
    """StatusChangeLog accepts inserts; ORM updates are rejected."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    assessment_id = uuid.uuid4()
    log_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        vacancy_id, topic_id, candidate_id, question_id = await _seed_graph(session)
        session.add(
            TopicAssessment(
                id=assessment_id,
                candidate_id=candidate_id,
                topic_id=topic_id,
                system_status=TopicStatus.NEEDS_CHECK,
                current_status=TopicStatus.NEEDS_CHECK,
                confidence=Confidence.LOW,
                reasoning_summary="Unclear answer",
            )
        )
        session.add(
            StatusChangeLog(
                id=log_id,
                assessment_id=assessment_id,
                author_id=uuid.uuid4(),
                author_role=AuthorRole.TECH_SPECIALIST,
                old_status=TopicStatus.NEEDS_CHECK,
                new_status=TopicStatus.CONFIRMED,
                comment="Evidence sufficient",
            )
        )
        await session.commit()

        log = await session.get(StatusChangeLog, log_id)
        assert log is not None
        assert log.new_status == TopicStatus.CONFIRMED

        log.comment = "tamper"
        with pytest.raises(RuntimeError, match="append-only"):
            await session.flush()
        await session.rollback()

        # re-open clean session for cleanup after rollback
        async with AsyncSessionLocal() as cleanup:
            await _cleanup_graph(
                cleanup,
                vacancy_id=vacancy_id,
                topic_id=topic_id,
                candidate_id=candidate_id,
                question_id=question_id,
            )


@pytest.mark.asyncio
async def test_interview_result_coverage_fields() -> None:
    """InterviewResult stores coverage triple and version metadata."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        vacancy_id, topic_id, candidate_id, question_id = await _seed_graph(session)
        session.add(
            InterviewResult(
                candidate_id=candidate_id,
                confirmed_count=3,
                needs_check_count=1,
                not_confirmed_count=0,
                mandatory_coverage=None,
                desired_coverage=Decimal("0.5000"),
                recommendation=Recommendation.NEEDS_ADDITIONAL_CHECK,
                vacancy_version=1,
                model_version="gpt-4o",
                prompt_version="assess-v1",
            )
        )
        await session.commit()

        result = await session.get(InterviewResult, candidate_id)
        assert result is not None
        assert result.confirmed_count == 3
        assert result.needs_check_count == 1
        assert result.mandatory_coverage is None
        assert result.recommendation == Recommendation.NEEDS_ADDITIONAL_CHECK

        await _cleanup_graph(
            session,
            vacancy_id=vacancy_id,
            topic_id=topic_id,
            candidate_id=candidate_id,
            question_id=question_id,
        )


@pytest.mark.asyncio
async def test_answer_assessment_column_sets() -> None:
    """PRD §5 columns exist on all four new tables."""
    get_settings.cache_clear()
    from app.db import engine

    async with engine.connect() as conn:

        def _columns(sync_conn: object, table: str) -> set[str]:
            return {col["name"] for col in inspect(sync_conn).get_columns(table)}

        answer_cols = await conn.run_sync(lambda c: _columns(c, "answer"))
        assessment_cols = await conn.run_sync(lambda c: _columns(c, "topic_assessment"))
        log_cols = await conn.run_sync(lambda c: _columns(c, "status_change_log"))
        result_cols = await conn.run_sync(lambda c: _columns(c, "interview_result"))

    assert answer_cols == {
        "id",
        "question_id",
        "video_url",
        "audio_url",
        "transcript",
        "transcript_segments",
        "duration_sec",
        "skipped",
        "technically_lost",
        "processing_status",
    }
    assert assessment_cols == {
        "id",
        "candidate_id",
        "topic_id",
        "system_status",
        "current_status",
        "confidence",
        "signals",
        "evidence",
        "reasoning_summary",
        "reviewed_by",
        "reviewer_comment",
    }
    assert log_cols == {
        "id",
        "assessment_id",
        "author_id",
        "author_role",
        "old_status",
        "new_status",
        "comment",
        "created_at",
    }
    assert result_cols == {
        "candidate_id",
        "confirmed_count",
        "needs_check_count",
        "not_confirmed_count",
        "mandatory_coverage",
        "desired_coverage",
        "recommendation",
        "vacancy_version",
        "model_version",
        "prompt_version",
    }
