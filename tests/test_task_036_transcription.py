"""Celery-задача транскрибации (M5): статусы, детект пустой дорожки, needs_check при error."""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.integrations.asr import ASRClientError, TranscriptionResult
from app.integrations.storage import S3StorageError
from app.models.answer import Answer, AnswerProcessingStatus
from app.models.candidate import Candidate
from app.models.question import Question, QuestionPattern, QuestionType
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.topic_assessment import AssessmentStatus, TopicAssessment
from app.models.vacancy import Vacancy, VacancyGrade
from app.services.transcription import transcribe_answer

AUDIO_URL = "s3://interviewer-media/answers/cand/upload/audio.webm"
AUDIO_KEY = "answers/cand/upload/audio.webm"


class FakeASR:
    def __init__(self, result: TranscriptionResult | None = None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.terms: list[str] | None = None

    async def transcribe(
        self, audio: bytes, *, filename: str = "answer.webm", terms=None, language=None
    ) -> TranscriptionResult:
        self.terms = list(terms or [])
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class FakeStorage:
    def __init__(self, data: dict[str, bytes]) -> None:
        self.data = data

    async def get_object_bytes(self, key: str) -> bytes:
        if key not in self.data:
            raise S3StorageError(message="missing", bucket="interviewer-media", key=key)
        return self.data[key]


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        yield db
    await engine.dispose()


async def _seed(session: AsyncSession, *, duration: int = 5) -> tuple[uuid.UUID, uuid.UUID]:
    vacancy = Vacancy(
        id=uuid.uuid4(), title="Backend", grade=VacancyGrade.MIDDLE, asr_terms=["Kafka"]
    )
    vacancy.lineage_id = vacancy.id
    topic = Topic(
        vacancy_id=vacancy.id,
        title="Kafka",
        skill_type=SkillType.HARD,
        importance=TopicImportance.MANDATORY,
        order=0,
    )
    vacancy.topics = [topic]
    candidate = Candidate(vacancy_id=vacancy.id)
    session.add_all([vacancy, candidate])
    await session.flush()
    question = Question(
        topic_id=topic.id, type=QuestionType.CORE, pattern=QuestionPattern.EXPERIENCE, text="Q"
    )
    session.add(question)
    await session.flush()
    answer = Answer(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        question_id=question.id,
        audio_url=AUDIO_URL,
        video_url="s3://interviewer-media/answers/cand/upload/video.webm",
        duration_sec=duration,
        processing_status=AnswerProcessingStatus.RECORDED,
    )
    session.add(answer)
    await session.commit()
    return candidate.id, answer.id


async def _needs_check(session: AsyncSession, candidate_id: uuid.UUID) -> TopicAssessment | None:
    return await session.scalar(
        select(TopicAssessment).where(TopicAssessment.candidate_id == candidate_id)
    )


@pytest.mark.anyio
async def test_transcribe_success_ready_with_segments(session: AsyncSession) -> None:
    candidate_id, answer_id = await _seed(session)
    asr = FakeASR(
        TranscriptionResult(
            text="Работал с Kafka в проде",
            segments=[{"text": "Работал с Kafka в проде", "start": 0.0, "end": 4.0}],
            model_version="whisper-1",
        )
    )
    storage = FakeStorage({AUDIO_KEY: b"x" * 4096})

    answer = await transcribe_answer(session, answer_id, asr_client=asr, storage=storage)

    assert answer is not None
    assert answer.processing_status == AnswerProcessingStatus.READY
    assert answer.transcript == "Работал с Kafka в проде"
    assert answer.transcript_segments[0]["start"] == 0.0
    assert asr.terms == ["Kafka"]  # словарь вакансии применён
    assert await _needs_check(session, candidate_id) is None


@pytest.mark.anyio
async def test_silence_transcript_marks_error_and_needs_check(session: AsyncSession) -> None:
    candidate_id, answer_id = await _seed(session)
    asr = FakeASR(TranscriptionResult(text="", segments=[], model_version="whisper-1"))
    storage = FakeStorage({AUDIO_KEY: b"x" * 4096})

    answer = await transcribe_answer(session, answer_id, asr_client=asr, storage=storage)

    assert answer is not None
    assert answer.processing_status == AnswerProcessingStatus.ERROR
    assessment = await _needs_check(session, candidate_id)
    assert assessment is not None
    assert assessment.system_status == AssessmentStatus.NEEDS_CHECK
    assert assessment.signals is None and assessment.evidence is None


@pytest.mark.anyio
async def test_too_short_audio_marks_error(session: AsyncSession) -> None:
    candidate_id, answer_id = await _seed(session)
    storage = FakeStorage({AUDIO_KEY: b"tiny"})
    asr = FakeASR(TranscriptionResult(text="x", segments=[{"text": "x"}], model_version="w"))

    answer = await transcribe_answer(session, answer_id, asr_client=asr, storage=storage)

    assert answer is not None
    assert answer.processing_status == AnswerProcessingStatus.ERROR
    assert asr.terms is None  # ASR не вызывался
    assert (await _needs_check(session, candidate_id)) is not None


@pytest.mark.anyio
async def test_asr_failure_marks_error(session: AsyncSession) -> None:
    candidate_id, answer_id = await _seed(session)
    storage = FakeStorage({AUDIO_KEY: b"x" * 4096})
    asr = FakeASR(error=ASRClientError("boom"))

    answer = await transcribe_answer(session, answer_id, asr_client=asr, storage=storage)

    assert answer is not None
    assert answer.processing_status == AnswerProcessingStatus.ERROR
    assert (await _needs_check(session, candidate_id)) is not None


@pytest.mark.anyio
async def test_missing_audio_object_marks_error(session: AsyncSession) -> None:
    candidate_id, answer_id = await _seed(session)
    storage = FakeStorage({})  # объекта нет
    asr = FakeASR(TranscriptionResult(text="x", segments=[{"text": "x"}], model_version="w"))

    answer = await transcribe_answer(session, answer_id, asr_client=asr, storage=storage)

    assert answer is not None
    assert answer.processing_status == AnswerProcessingStatus.ERROR
    assert (await _needs_check(session, candidate_id)) is not None


def test_transcription_task_registered() -> None:
    from app.celery_app import celery_app

    assert "app.transcribe_answer" in celery_app.tasks
