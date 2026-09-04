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


class ProcessingStatus(StrEnum):
    RECORDED = "recorded"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    READY = "ready"
    ERROR = "error"


class TopicStatus(StrEnum):
    CONFIRMED = "confirmed"
    NEEDS_CHECK = "needs_check"
    NOT_CONFIRMED = "not_confirmed"
    OUT_OF_SCOPE = "out_of_scope"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AuthorRole(StrEnum):
    SYSTEM = "system"
    RECRUITER = "recruiter"
    TECH_SPECIALIST = "tech_specialist"
    HIRING_MANAGER = "hiring_manager"


class Recommendation(StrEnum):
    SUITABLE = "suitable"
    NOT_SUITABLE = "not_suitable"
    NEEDS_ADDITIONAL_CHECK = "needs_additional_check"
