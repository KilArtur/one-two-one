"""ORM-модели доменной области — импортируются, чтобы попасть в метадату Alembic."""

from app.models.answer import Answer, AnswerProcessingStatus
from app.models.answer_upload import AnswerUpload
from app.models.candidate import Candidate, CandidateStatus
from app.models.data_deletion import DataDeletionLog
from app.models.interview_link import InterviewLink
from app.models.interview_result import InterviewRecommendation, InterviewResult
from app.models.question import Question, QuestionPattern, QuestionType
from app.models.result_link import ResultLink
from app.models.stop_factor import StopFactorFlag
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.topic_assessment import (
    AssessmentConfidence,
    AssessmentStatus,
    ReviewerRole,
    StatusChangeLog,
    TopicAssessment,
)
from app.models.vacancy import Vacancy, VacancyGrade, VacancyStatus
from app.models.video_view import VideoViewLog

__all__ = [
    "ResultLink",
    "VideoViewLog",
    "Answer",
    "AnswerUpload",
    "AnswerProcessingStatus",
    "AssessmentConfidence",
    "AssessmentStatus",
    "Candidate",
    "CandidateStatus",
    "DataDeletionLog",
    "InterviewRecommendation",
    "InterviewLink",
    "InterviewResult",
    "Question",
    "QuestionPattern",
    "QuestionType",
    "ReviewerRole",
    "SkillType",
    "StatusChangeLog",
    "StopFactorFlag",
    "Topic",
    "TopicAssessment",
    "TopicImportance",
    "Vacancy",
    "VacancyGrade",
    "VacancyStatus",
]
