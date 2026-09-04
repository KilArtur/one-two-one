"""Domain enums for ORM models (PRD §5)."""

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


class CandidateStatus(StrEnum):
    INVITED = "invited"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    PROCESSED = "processed"
    REVIEWED = "reviewed"


class QuestionType(StrEnum):
    CORE = "core"
    PERSONAL = "personal"
    FOLLOW_UP = "follow_up"


class QuestionPattern(StrEnum):
    TECHNICAL = "technical"
    EXPERIENCE = "experience"
    REASONING = "reasoning"
