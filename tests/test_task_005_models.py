"""Проверки моделей Candidate, InterviewLink и Question: поля, enum, FK и self-FK."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import (
    Candidate,
    CandidateStatus,
    InterviewLink,
    Question,
    QuestionPattern,
    QuestionType,
    SkillType,
    Topic,
    TopicImportance,
    Vacancy,
    VacancyGrade,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
VERSIONS_DIR = ROOT_DIR / "backend" / "alembic" / "versions"


def _seed_interview() -> tuple[Candidate, InterviewLink, Question, Question]:
    """Создаёт схему во временной SQLite-БД и сохраняет кандидата, ссылку и два вопроса."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        vacancy = Vacancy(title="Backend-разработчик", grade=VacancyGrade.MIDDLE)
        topic = Topic(
            vacancy=vacancy,
            title="Kafka в production",
            skill_type=SkillType.HARD,
            importance=TopicImportance.MANDATORY,
        )
        candidate = Candidate(vacancy=vacancy, resume_text="Опыт с Kafka 3 года")
        link = InterviewLink(
            candidate=candidate,
            token=uuid.uuid4().hex,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        core_question = Question(
            topic=topic,
            type=QuestionType.CORE,
            pattern=QuestionPattern.EXPERIENCE,
            text="Расскажите, как вы эксплуатировали Kafka под нагрузкой",
            source_reason="Проверяет требование топика «Kafka в production»",
        )
        follow_up = Question(
            topic=topic,
            type=QuestionType.FOLLOW_UP,
            pattern=QuestionPattern.REASONING,
            text="Какой был ваш личный вклад в настройку партиционирования?",
            parent=core_question,
        )
        session.add_all([vacancy, candidate, core_question, follow_up])
        session.commit()

        stored_candidate = session.execute(
            select(Candidate).where(Candidate.id == candidate.id)
        ).scalar_one()
        stored_link = session.execute(
            select(InterviewLink).where(InterviewLink.id == link.id)
        ).scalar_one()
        stored_core = session.execute(
            select(Question).where(Question.id == core_question.id)
        ).scalar_one()
        stored_follow_up = session.execute(
            select(Question).where(Question.id == follow_up.id)
        ).scalar_one()

    engine.dispose()
    return stored_candidate, stored_link, stored_core, stored_follow_up


@pytest.fixture(scope="module")
def seeded() -> tuple[Candidate, InterviewLink, Question, Question]:
    return _seed_interview()


def test_candidate_has_all_prd_columns() -> None:
    columns = set(inspect(Candidate).columns.keys())

    assert {
        "id",
        "vacancy_id",
        "resume_text",
        "resume_file_url",
        "consent_given_at",
        "status",
    } <= columns


def test_interview_link_has_all_prd_columns() -> None:
    columns = set(inspect(InterviewLink).columns.keys())

    assert {"id", "candidate_id", "token", "expires_at", "used_at", "revoked"} <= columns


def test_question_has_all_prd_columns() -> None:
    columns = set(inspect(Question).columns.keys())

    assert {
        "id",
        "topic_id",
        "type",
        "pattern",
        "text",
        "source_reason",
        "reviewed_by_expert",
        "parent_question_id",
    } <= columns


def test_enum_values_match_prd() -> None:
    assert [status.value for status in CandidateStatus] == [
        "invited",
        "in_progress",
        "submitted",
        "processed",
        "reviewed",
    ]
    assert [question_type.value for question_type in QuestionType] == [
        "core",
        "personal",
        "follow_up",
    ]
    assert [pattern.value for pattern in QuestionPattern] == [
        "technical",
        "experience",
        "reasoning",
    ]


def test_enum_columns_store_values_not_names() -> None:
    """В БД пишется значение члена enum (например in_progress), а не его имя."""
    status_column = inspect(Candidate).columns["status"].type

    assert status_column.enums == [status.value for status in CandidateStatus]
    assert status_column.name == "candidate_status"


def test_foreign_keys_point_to_parent_tables() -> None:
    candidate_fk = next(iter(inspect(Candidate).columns["vacancy_id"].foreign_keys))
    link_fk = next(iter(inspect(InterviewLink).columns["candidate_id"].foreign_keys))
    question_fk = next(iter(inspect(Question).columns["topic_id"].foreign_keys))

    assert candidate_fk.target_fullname == "vacancy.id"
    assert link_fk.target_fullname == "candidate.id"
    assert question_fk.target_fullname == "topic.id"
    assert {candidate_fk.ondelete, link_fk.ondelete, question_fk.ondelete} == {"CASCADE"}


def test_question_parent_is_self_referential() -> None:
    column = inspect(Question).columns["parent_question_id"]
    foreign_key = next(iter(column.foreign_keys))

    assert foreign_key.target_fullname == "question.id"
    assert column.nullable is True


def test_candidate_status_defaults_to_invited(
    seeded: tuple[Candidate, InterviewLink, Question, Question],
) -> None:
    candidate, _, _, _ = seeded

    assert candidate.status == CandidateStatus.INVITED
    assert candidate.consent_given_at is None


def test_interview_link_persists_unused_and_not_revoked(
    seeded: tuple[Candidate, InterviewLink, Question, Question],
) -> None:
    candidate, link, _, _ = seeded

    assert link.candidate_id == candidate.id
    assert link.used_at is None
    assert link.revoked is False
    assert [stored.id for stored in candidate.interview_links] == [link.id]


def test_interview_link_token_is_unique() -> None:
    column = inspect(InterviewLink).columns["token"]

    assert column.unique is True


def test_follow_up_links_to_parent_question(
    seeded: tuple[Candidate, InterviewLink, Question, Question],
) -> None:
    _, _, core_question, follow_up = seeded

    assert core_question.parent_question_id is None
    assert core_question.reviewed_by_expert is False
    assert follow_up.type == QuestionType.FOLLOW_UP
    assert follow_up.parent_question_id == core_question.id
    assert follow_up.topic_id == core_question.topic_id


def test_migration_creates_candidate_link_and_question() -> None:
    revision = (VERSIONS_DIR / "a7feac956a32_candidate_link_and_question_tables.py").read_text()

    assert 'down_revision: str | Sequence[str] | None = "f7db7e0c8e3e"' in revision
    assert 'op.create_table(\n        "candidate"' in revision
    assert 'op.create_table(\n        "interview_link"' in revision
    assert 'op.create_table(\n        "question"' in revision
    assert (
        'sa.ForeignKeyConstraint(["parent_question_id"], ["question.id"], ondelete="CASCADE")'
        in revision
    )
