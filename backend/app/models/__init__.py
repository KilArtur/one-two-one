"""ORM-модели доменной области — импортируются, чтобы попасть в метадату Alembic."""

from app.models.answer import Answer, AnswerProcessingStatus
from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_link import InterviewLink
from app.models.interview_result import InterviewRecommendation, InterviewResult
from app.models.question import Question, QuestionPattern, QuestionType
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.topic_assessment import (
    AssessmentConfidence,
    AssessmentStatus,
    ReviewerRole,
    StatusChangeLog,
    TopicAssessment,
)
from app.models.vacancy import Vacancy, VacancyGrade, VacancyStatus

__all__ = [
    "Answer",
    "AnswerProcessingStatus",
    "AssessmentConfidence",
    "AssessmentStatus",
    "Candidate",
    "CandidateStatus",
    "InterviewRecommendation",
    "InterviewLink",
    "InterviewResult",
    "Question",
    "QuestionPattern",
    "QuestionType",
    "ReviewerRole",
    "SkillType",
    "StatusChangeLog",
    "Topic",
    "TopicAssessment",
    "TopicImportance",
    "Vacancy",
    "VacancyGrade",
    "VacancyStatus",
]
