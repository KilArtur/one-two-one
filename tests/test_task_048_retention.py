"""Автоудаление по ретенции 6 месяцев (Р18): удаление ПДн, сохранение агрегатов (TASK-048)."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.answer import Answer, AnswerProcessingStatus
from app.models.candidate import Candidate
from app.models.data_deletion import DataDeletionLog
from app.models.interview_result import InterviewRecommendation, InterviewResult
from app.models.question import Question, QuestionPattern, QuestionType
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.vacancy import Vacancy, VacancyGrade
from app.services.retention import purge_candidate, purge_expired


class FakeStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def delete_object(self, key: str) -> None:
        self.deleted.append(key)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        yield db
    await engine.dispose()


async def _seed(session: AsyncSession, *, created_at: datetime) -> uuid.UUID:
    vacancy = Vacancy(id=uuid.uuid4(), title="Backend", grade=VacancyGrade.MIDDLE)
    vacancy.lineage_id = vacancy.id
    candidate = Candidate(
        vacancy_id=vacancy.id, resume_text="Резюме кандидата", resume_file_url="s3://b/resume.pdf"
    )
    candidate.created_at = created_at
    topic = Topic(
        vacancy_id=vacancy.id, title="PostgreSQL", skill_type=SkillType.HARD,
        importance=TopicImportance.MANDATORY, order=0,
    )
    vacancy.topics = [topic]
    session.add_all([vacancy, candidate])
    await session.flush()
    question = Question(
        topic_id=topic.id, type=QuestionType.CORE, pattern=QuestionPattern.EXPERIENCE, text="Q"
    )
    session.add(question)
    await session.flush()
    answer = Answer(
        id=uuid.uuid4(), candidate_id=candidate.id, question_id=question.id,
        video_url="s3://interviewer-media/answers/c/u/video.webm",
        audio_url="s3://interviewer-media/answers/c/u/audio.webm",
        transcript="Я работал с PostgreSQL",
        transcript_segments=[{"text": "Я работал с PostgreSQL", "start": 0.0, "end": 3.0}],
        duration_sec=5, processing_status=AnswerProcessingStatus.READY,
    )
    session.add(answer)
    result = InterviewResult(
        candidate_id=candidate.id, recommendation=InterviewRecommendation.FIT,
        vacancy_version=1, model_version="m", prompt_version="p",
    )
    session.add(result)
    await session.commit()
    return candidate.id


@pytest.mark.anyio
async def test_expired_candidate_purged_aggregate_kept(session: AsyncSession) -> None:
    old = datetime.now(UTC) - timedelta(days=200)
    candidate_id = await _seed(session, created_at=old)
    storage = FakeStorage()

    purged = await purge_expired(session, storage)

    assert candidate_id in purged
    # Шаг 1: медиа удалены из S3 и очищены в БД
    assert len(storage.deleted) == 2
    answer = await session.scalar(select(Answer).where(Answer.candidate_id == candidate_id))
    assert answer.video_url is None and answer.audio_url is None
    assert answer.transcript is None and answer.transcript_segments is None
    candidate = await session.get(Candidate, candidate_id)
    assert candidate.resume_text is None and candidate.resume_file_url is None
    # Шаг 2: обезличенный агрегат сохранён
    assert await session.get(InterviewResult, candidate_id) is not None
    # факт удаления залогирован
    assert (
        await session.scalar(
            select(func.count()).select_from(DataDeletionLog).where(
                DataDeletionLog.candidate_id == candidate_id
            )
        )
        == 1
    )


@pytest.mark.anyio
async def test_recent_candidate_not_purged(session: AsyncSession) -> None:
    recent = datetime.now(UTC) - timedelta(days=10)
    candidate_id = await _seed(session, created_at=recent)
    storage = FakeStorage()

    purged = await purge_expired(session, storage)

    assert candidate_id not in purged
    assert storage.deleted == []
    candidate = await session.get(Candidate, candidate_id)
    assert candidate.resume_text == "Резюме кандидата"


@pytest.mark.anyio
async def test_retention_is_idempotent(session: AsyncSession) -> None:
    old = datetime.now(UTC) - timedelta(days=200)
    candidate_id = await _seed(session, created_at=old)
    storage = FakeStorage()

    first = await purge_expired(session, storage)
    second = await purge_expired(session, storage)

    assert candidate_id in first
    assert candidate_id not in second  # больше нечего удалять — повторно не логируем
    total_logs = await session.scalar(
        select(func.count()).select_from(DataDeletionLog).where(
            DataDeletionLog.candidate_id == candidate_id
        )
    )
    assert total_logs == 1


@pytest.mark.anyio
async def test_on_request_purge_logs(session: AsyncSession) -> None:
    # Шаг 3: досрочное удаление по запросу — данные стёрты, факт залогирован
    candidate_id = await _seed(session, created_at=datetime.now(UTC) - timedelta(days=5))
    storage = FakeStorage()

    log = await purge_candidate(
        session, storage, candidate_id, reason="on_request", force_log=True
    )

    assert log is not None and log.reason == "on_request"
    candidate = await session.get(Candidate, candidate_id)
    assert candidate.resume_text is None
    assert await session.get(InterviewResult, candidate_id) is not None


def test_retention_task_and_beat_registered() -> None:
    from app.celery_app import celery_app

    assert "app.purge_expired_data" in celery_app.tasks
    assert "purge-expired-data" in celery_app.conf.beat_schedule
