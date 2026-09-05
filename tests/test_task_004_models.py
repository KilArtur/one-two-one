"""Проверки ORM-моделей Vacancy и Topic: поля, enum-значения, дефолты и FK."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import (
    SkillType,
    Topic,
    TopicImportance,
    Vacancy,
    VacancyGrade,
    VacancyStatus,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
VERSIONS_DIR = ROOT_DIR / "backend" / "alembic" / "versions"


def _seed_vacancy_with_topic() -> tuple[Vacancy, Topic]:
    """Создаёт схему во временной SQLite-БД и сохраняет вакансию с топиком."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        vacancy = Vacancy(
            title="Backend-разработчик",
            grade=VacancyGrade.MIDDLE_PLUS,
            tasks="Разработка сервисов на FastAPI",
            specialist_profile="Профиль от техлида",
        )
        topic = Topic(
            vacancy=vacancy,
            title="Kafka в production",
            skill_type=SkillType.HARD,
            importance=TopicImportance.MANDATORY,
            requirement_description="Опыт эксплуатации Kafka под нагрузкой",
            depth_expectations="Партиционирование, ретраи, мониторинг лага",
            order=1,
        )
        session.add(vacancy)
        session.commit()

        stored = session.execute(select(Vacancy).where(Vacancy.id == vacancy.id)).scalar_one()
        stored_topic = session.execute(select(Topic).where(Topic.id == topic.id)).scalar_one()

    engine.dispose()
    return stored, stored_topic


@pytest.fixture(scope="module")
def seeded() -> tuple[Vacancy, Topic]:
    return _seed_vacancy_with_topic()


def test_vacancy_has_all_prd_columns() -> None:
    columns = set(inspect(Vacancy).columns.keys())

    assert {
        "id",
        "title",
        "grade",
        "tasks",
        "specialist_profile",
        "version",
        "status",
    } <= columns


def test_topic_has_all_prd_columns() -> None:
    columns = set(inspect(Topic).columns.keys())

    assert {
        "id",
        "vacancy_id",
        "title",
        "skill_type",
        "importance",
        "requirement_description",
        "depth_expectations",
        "verifiable_by_interview",
        "order",
    } <= columns


def test_enum_values_match_prd() -> None:
    assert [grade.value for grade in VacancyGrade] == ["junior", "middle", "middle+", "senior"]
    assert [status.value for status in VacancyStatus] == ["draft", "active", "archived"]
    assert [skill.value for skill in SkillType] == ["hard", "soft"]
    assert [importance.value for importance in TopicImportance] == ["mandatory", "desired"]


def test_enum_columns_store_values_not_names() -> None:
    """В БД пишется значение члена enum (например middle+), а не его имя."""
    grade_column = inspect(Vacancy).columns["grade"].type

    assert grade_column.enums == ["junior", "middle", "middle+", "senior"]
    assert grade_column.name == "vacancy_grade"


def test_topic_has_foreign_key_to_vacancy() -> None:
    foreign_key = next(iter(inspect(Topic).columns["vacancy_id"].foreign_keys))

    assert foreign_key.target_fullname == "vacancy.id"
    assert foreign_key.ondelete == "CASCADE"


def test_verifiable_by_interview_defaults_to_true() -> None:
    column = inspect(Topic).columns["verifiable_by_interview"]

    assert column.default.arg is True
    assert "true" in str(column.server_default.arg).lower()


def test_vacancy_version_starts_at_one() -> None:
    column = inspect(Vacancy).columns["version"]

    assert column.default.arg == 1


def test_vacancy_persists_with_defaults(seeded: tuple[Vacancy, Topic]) -> None:
    vacancy, _ = seeded

    assert vacancy.grade == VacancyGrade.MIDDLE_PLUS
    assert vacancy.status == VacancyStatus.DRAFT
    assert vacancy.version == 1


def test_topic_persists_and_links_to_vacancy(seeded: tuple[Vacancy, Topic]) -> None:
    vacancy, topic = seeded

    assert topic.vacancy_id == vacancy.id
    assert topic.skill_type == SkillType.HARD
    assert topic.importance == TopicImportance.MANDATORY
    assert topic.verifiable_by_interview is True
    assert [linked.id for linked in vacancy.topics] == [topic.id]


def test_migration_creates_vacancy_and_topic() -> None:
    revision = (VERSIONS_DIR / "f7db7e0c8e3e_vacancy_and_topic_tables.py").read_text()

    assert 'down_revision: str | Sequence[str] | None = "11d73faaed8f"' in revision
    assert 'op.create_table(\n        "vacancy"' in revision
    assert 'op.create_table(\n        "topic"' in revision
    assert 'sa.ForeignKeyConstraint(["vacancy_id"], ["vacancy.id"], ondelete="CASCADE")' in revision
