"""Проверки моделей Answer, TopicAssessment, StatusChangeLog и InterviewResult."""

import asyncio
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base
from app.models import (
    Answer,
    AnswerProcessingStatus,
    AssessmentConfidence,
    AssessmentStatus,
    Candidate,
    InterviewRecommendation,
    InterviewResult,
    Question,
    QuestionPattern,
    QuestionType,
    ReviewerRole,
    SkillType,
    StatusChangeLog,
    Topic,
    TopicAssessment,
    TopicImportance,
    Vacancy,
    VacancyGrade,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
VERSIONS_DIR = ROOT_DIR / "backend" / "alembic" / "versions"


async def _seed_assessment_graph() -> tuple[
    Answer,
    TopicAssessment,
    StatusChangeLog,
    InterviewResult,
    Candidate,
    Question,
]:
    """Создаёт схему во временной SQLite-БД и сохраняет полный граф сущностей TASK-006."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        vacancy = Vacancy(title="Backend-разработчик", grade=VacancyGrade.SENIOR)
        topic = Topic(
            vacancy=vacancy,
            title="Kafka в production",
            skill_type=SkillType.HARD,
            importance=TopicImportance.MANDATORY,
        )
        candidate = Candidate(vacancy=vacancy, resume_text="10 лет backend-разработки")
        question = Question(
            topic=topic,
            type=QuestionType.CORE,
            pattern=QuestionPattern.EXPERIENCE,
            text="Расскажите про эксплуатацию Kafka под нагрузкой",
        )
        session.add_all([vacancy, candidate, question])
        await session.flush()
        answer = Answer(
            question=question,
            video_url="s3://videos/answer-1.mp4",
            audio_url="s3://audio/answer-1.wav",
            transcript="Мы держали 30k msg/s и настраивали ретраи.",
            transcript_segments=[
                {"start_sec": 0.0, "end_sec": 4.2, "text": "Мы держали 30k msg/s"}
            ],
            duration_sec=57,
        )
        assessment = TopicAssessment(
            candidate=candidate,
            topic=topic,
            system_status=AssessmentStatus.CONFIRMED,
            current_status=AssessmentStatus.NEEDS_CHECK,
            confidence=AssessmentConfidence.MEDIUM,
            signals={
                "correctness": "high",
                "example": "high",
                "personal_contribution": "medium",
            },
            evidence=[
                {
                    "question_id": str(question.id),
                    "quote": "Мы держали 30k msg/s",
                    "start_sec": 0.0,
                    "end_sec": 2.0,
                }
            ],
            reasoning_summary="Есть практический пример, но личный вклад стоит перепроверить.",
            reviewed_by=uuid.uuid4(),
            reviewer_comment="Нужно проверить глубину участия в настройке.",
        )
        change_log = StatusChangeLog(
            assessment=assessment,
            author_id=uuid.uuid4(),
            author_role=ReviewerRole.TECH_SPECIALIST,
            old_status=AssessmentStatus.CONFIRMED,
            new_status=AssessmentStatus.NEEDS_CHECK,
            comment="Сомнение в личном вкладе",
        )
        result = InterviewResult(
            candidate=candidate,
            confirmed_count=1,
            needs_check_count=0,
            not_confirmed_count=0,
            mandatory_coverage=Decimal("1.0000"),
            desired_coverage=Decimal("1.0000"),
            recommendation=InterviewRecommendation.FIT,
            vacancy_version=3,
            model_version="gpt-4o-2026-08-01",
            prompt_version="topic-assessment-v1",
        )
        session.add_all([answer, assessment, change_log, result])
        await session.commit()

        stored_answer = (
            await session.execute(select(Answer).where(Answer.id == answer.id))
        ).scalar_one()
        stored_assessment = (
            await session.execute(
                select(TopicAssessment).where(TopicAssessment.id == assessment.id)
            )
        ).scalar_one()
        stored_log = (
            await session.execute(
                select(StatusChangeLog).where(StatusChangeLog.id == change_log.id)
            )
        ).scalar_one()
        stored_result = (
            await session.execute(
                select(InterviewResult).where(InterviewResult.candidate_id == candidate.id)
            )
        ).scalar_one()
        stored_candidate = (
            await session.execute(select(Candidate).where(Candidate.id == candidate.id))
        ).scalar_one()
        stored_question = (
            await session.execute(select(Question).where(Question.id == question.id))
        ).scalar_one()

    await engine.dispose()
    return (
        stored_answer,
        stored_assessment,
        stored_log,
        stored_result,
        stored_candidate,
        stored_question,
    )


@pytest.fixture(scope="module")
def seeded() -> tuple[
    Answer, TopicAssessment, StatusChangeLog, InterviewResult, Candidate, Question
]:
    return asyncio.run(_seed_assessment_graph())


def test_answer_has_all_prd_columns() -> None:
    columns = set(inspect(Answer).columns.keys())

    assert {
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
    } <= columns


def test_topic_assessment_has_all_prd_columns() -> None:
    columns = set(inspect(TopicAssessment).columns.keys())

    assert {
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
    } <= columns


def test_status_change_log_has_all_prd_columns() -> None:
    columns = set(inspect(StatusChangeLog).columns.keys())

    assert {
        "id",
        "assessment_id",
        "author_id",
        "author_role",
        "old_status",
        "new_status",
        "comment",
        "created_at",
    } <= columns
    assert "updated_at" not in columns


def test_interview_result_has_all_prd_columns() -> None:
    columns = set(inspect(InterviewResult).columns.keys())

    assert {
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
    } <= columns


def test_enum_values_match_prd() -> None:
    assert [status.value for status in AnswerProcessingStatus] == [
        "recorded",
        "transcribing",
        "analyzing",
        "ready",
        "error",
    ]
    assert [status.value for status in AssessmentStatus] == [
        "confirmed",
        "needs_check",
        "not_confirmed",
        "out_of_scope",
    ]
    assert [confidence.value for confidence in AssessmentConfidence] == ["high", "medium", "low"]
    assert [role.value for role in ReviewerRole] == [
        "recruiter",
        "technical_specialist",
        "hiring_manager",
    ]
    assert [recommendation.value for recommendation in InterviewRecommendation] == [
        "fit",
        "additional_check",
        "not_fit",
    ]


def test_topic_assessment_uses_distinct_system_and_current_status_columns() -> None:
    system_status = inspect(TopicAssessment).columns["system_status"]
    current_status = inspect(TopicAssessment).columns["current_status"]

    assert system_status.name == "system_status"
    assert current_status.name == "current_status"
    assert system_status.type.name == current_status.type.name == "assessment_status"


def test_foreign_keys_and_uniqueness_match_domain_constraints() -> None:
    answer_fk = next(iter(inspect(Answer).columns["question_id"].foreign_keys))
    candidate_fk = next(iter(inspect(TopicAssessment).columns["candidate_id"].foreign_keys))
    topic_fk = next(iter(inspect(TopicAssessment).columns["topic_id"].foreign_keys))
    log_fk = next(iter(inspect(StatusChangeLog).columns["assessment_id"].foreign_keys))
    result_fk = next(iter(inspect(InterviewResult).columns["candidate_id"].foreign_keys))
    unique_constraints = {
        constraint.name for constraint in inspect(TopicAssessment).local_table.constraints
    }

    assert answer_fk.target_fullname == "question.id"
    assert candidate_fk.target_fullname == "candidate.id"
    assert topic_fk.target_fullname == "topic.id"
    assert log_fk.target_fullname == "topic_assessment.id"
    assert result_fk.target_fullname == "candidate.id"
    assert {
        answer_fk.ondelete,
        candidate_fk.ondelete,
        topic_fk.ondelete,
        log_fk.ondelete,
        result_fk.ondelete,
    } == {"CASCADE"}
    assert "uq_topic_assessment_candidate_topic" in unique_constraints


def test_answer_and_assessment_persist_json_and_defaults(
    seeded: tuple[Answer, TopicAssessment, StatusChangeLog, InterviewResult, Candidate, Question],
) -> None:
    answer, assessment, _, _, _, question = seeded

    assert answer.question_id == question.id
    assert answer.processing_status == AnswerProcessingStatus.RECORDED
    assert answer.skipped is False
    assert answer.technically_lost is False
    assert answer.transcript_segments == [
        {"start_sec": 0.0, "end_sec": 4.2, "text": "Мы держали 30k msg/s"}
    ]
    assert assessment.system_status == AssessmentStatus.CONFIRMED
    assert assessment.current_status == AssessmentStatus.NEEDS_CHECK
    assert assessment.confidence == AssessmentConfidence.MEDIUM
    assert assessment.signals == {
        "correctness": "high",
        "example": "high",
        "personal_contribution": "medium",
    }
    assert assessment.evidence == [
        {
            "question_id": str(question.id),
            "quote": "Мы держали 30k msg/s",
            "start_sec": 0.0,
            "end_sec": 2.0,
        }
    ]


def test_status_change_log_is_append_only_shape(
    seeded: tuple[Answer, TopicAssessment, StatusChangeLog, InterviewResult, Candidate, Question],
) -> None:
    _, assessment, change_log, _, _, _ = seeded

    assert change_log.assessment_id == assessment.id
    assert change_log.author_role == ReviewerRole.TECH_SPECIALIST
    assert change_log.old_status == AssessmentStatus.CONFIRMED
    assert change_log.new_status == AssessmentStatus.NEEDS_CHECK
    assert [entry.id for entry in assessment.status_changes] == [change_log.id]


def test_interview_result_persists_deterministic_snapshot(
    seeded: tuple[Answer, TopicAssessment, StatusChangeLog, InterviewResult, Candidate, Question],
) -> None:
    _, _, _, result, candidate, _ = seeded

    assert result.candidate_id == candidate.id
    assert result.confirmed_count == 1
    assert result.needs_check_count == 0
    assert result.not_confirmed_count == 0
    assert result.mandatory_coverage == Decimal("1.0000")
    assert result.desired_coverage == Decimal("1.0000")
    assert result.recommendation == InterviewRecommendation.FIT
    assert result.vacancy_version == 3
    assert result.model_version == "gpt-4o-2026-08-01"
    assert result.prompt_version == "topic-assessment-v1"
    assert candidate.interview_result is not None


def test_question_and_candidate_relationships_include_task_006_entities(
    seeded: tuple[Answer, TopicAssessment, StatusChangeLog, InterviewResult, Candidate, Question],
) -> None:
    answer, assessment, _, _, candidate, question = seeded

    assert [stored.id for stored in question.answers] == [answer.id]
    assert [stored.id for stored in candidate.topic_assessments] == [assessment.id]


def test_migration_creates_answer_assessment_log_and_result() -> None:
    revision = (VERSIONS_DIR / "4ae9c5a1f2d0_answer_assessment_and_result_tables.py").read_text()

    assert 'down_revision: str | Sequence[str] | None = "a7feac956a32"' in revision
    assert 'op.create_table(\n        "answer"' in revision
    assert 'op.create_table(\n        "topic_assessment"' in revision
    assert 'op.create_table(\n        "status_change_log"' in revision
    assert 'op.create_table(\n        "interview_result"' in revision
    assert '"transcript_segments", postgresql.JSONB' in revision
    assert '"signals", postgresql.JSONB' in revision
    assert '"evidence", postgresql.JSONB' in revision
    assert '"system_status"' in revision and '"current_status"' in revision
