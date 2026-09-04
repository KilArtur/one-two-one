"""Domain enums for Vacancy and Topic (PRD §5)."""

from enum import StrEnum


class VacancyGrade(StrEnum):
    JUNIOR = "junior"
    MIDDLE = "middle"
    MIDDLE_PLUS = "middle+"
    SENIOR = "senior"


class VacancyStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class SkillType(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class Importance(StrEnum):
    MANDATORY = "mandatory"
    DESIRED = "desired"
