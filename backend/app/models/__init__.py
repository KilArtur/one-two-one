"""ORM-модели доменной области — импортируются, чтобы попасть в метадату Alembic."""

from app.models.topic import SkillType, Topic, TopicImportance
from app.models.vacancy import Vacancy, VacancyGrade, VacancyStatus

__all__ = [
    "SkillType",
    "Topic",
    "TopicImportance",
    "Vacancy",
    "VacancyGrade",
    "VacancyStatus",
]
