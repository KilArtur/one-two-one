"""Оркестрация пайплайна: статусы, graceful-сбой LLM, сборка результата (TASK-037)."""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.integrations.asr import TranscriptionResult
from app.integrations.llm import LLMClientError, LLMInvocationResult
from app.integrations.storage import S3StorageError
from app.models.answer import Answer, AnswerProcessingStatus
from app.models.candidate import Candidate
from app.models.interview_result import InterviewRecommendation, InterviewResult
from app.models.question import Question, QuestionPattern, QuestionType
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.topic_assessment import AssessmentStatus, TopicAssessment
from app.models.vacancy import Vacancy, VacancyGrade
from app.schemas.assessment import TopicAssessmentLLM
from app.services.pipeline import process_answer

AUDIO_KEY = "answers/c/u/audio.webm"
AUDIO_URL = "s3://interviewer-media/answers/c/u/audio.webm"


class FakeASR:
    async def transcribe(self, audio, *, filename="a.webm", terms=None, language=None):
        return TranscriptionResult(
            text="Работал с PostgreSQL",
            segments=[{"text": "Работал с PostgreSQL", "start": 0.0, "end": 3.0}],
            model_version="whisper-1",
        )


class FakeStorage:
    def __init__(self, data: dict[str, bytes]) -> None:
        self.data = data

    async def get_object_bytes(self, key: str) -> bytes:
        if key not in self.data:
            raise S3StorageError(message="missing", bucket="b", key=key)
        return self.data[key]


class FakeLLM:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def generate_structured(self, prompt, *, schema, prompt_version, use_fast_model=False):
        if self.error is not None:
            raise self.error
        return LLMInvocationResult(
            content=TopicAssessmentLLM(
                correctness=True,
                example=True,
                personal_contribution=True,
                confidence="high",
                explicit_no_experience=False,
                technical_error=False,
                evidence_quote="Работал с PostgreSQL",
                reasoning_summary="ok",
            ),
            model_version="fake",
            prompt_version=prompt_version,
        )


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


async def _seed(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    vacancy = Vacancy(id=uuid.uuid4(), title="Backend", grade=VacancyGrade.MIDDLE)
    vacancy.lineage_id = vacancy.id
    topic = Topic(
        vacancy_id=vacancy.id,
        title="PostgreSQL",
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
        duration_sec=5,
        processing_status=AnswerProcessingStatus.RECORDED,
    )
    session.add(answer)
    await session.commit()
    return candidate.id, answer.id


async def _assessment(session, candidate_id):
    return await session.scalar(
        select(TopicAssessment).where(TopicAssessment.candidate_id == candidate_id)
    )


@pytest.mark.anyio
async def test_pipeline_end_to_end_ready(session: AsyncSession) -> None:
    candidate_id, answer_id = await _seed(session)
    answer = await process_answer(
        session,
        answer_id,
        asr_client=FakeASR(),
        llm_client=FakeLLM(),
        storage=FakeStorage({AUDIO_KEY: b"x" * 4096}),
    )
    assert answer is not None
    assert answer.processing_status == AnswerProcessingStatus.READY  # Шаг 1
    assert answer.transcript
    assessment = await _assessment(session, candidate_id)
    assert assessment.system_status == AssessmentStatus.CONFIRMED
    result = await session.get(InterviewResult, candidate_id)  # результат собран
    assert result is not None
    assert result.recommendation == InterviewRecommendation.FIT


@pytest.mark.anyio
async def test_pipeline_status_visible_after_stages(session: AsyncSession) -> None:
    candidate_id, answer_id = await _seed(session)
    await process_answer(
        session,
        answer_id,
        asr_client=FakeASR(),
        llm_client=FakeLLM(),
        storage=FakeStorage({AUDIO_KEY: b"x" * 4096}),
    )
    # Шаг 2: текущий статус обработки читается по кандидату
    answer = await session.scalar(select(Answer).where(Answer.candidate_id == candidate_id))
    assert answer.processing_status == AnswerProcessingStatus.READY


@pytest.mark.anyio
async def test_llm_failure_does_not_block_topic_closed(session: AsyncSession) -> None:
    candidate_id, answer_id = await _seed(session)
    answer = await process_answer(
        session,
        answer_id,
        asr_client=FakeASR(),
        llm_client=FakeLLM(error=LLMClientError("x", "m", "p", "u")),
        storage=FakeStorage({AUDIO_KEY: b"x" * 4096}),
    )
    assert answer is not None
    assert answer.processing_status == AnswerProcessingStatus.READY  # пайплайн не висит
    assessment = await _assessment(session, candidate_id)
    assert assessment.system_status == AssessmentStatus.NEEDS_CHECK  # топик закрыт по данным
    result = await session.get(InterviewResult, candidate_id)
    assert result.recommendation == InterviewRecommendation.ADDITIONAL_CHECK


@pytest.mark.anyio
async def test_transcription_error_graceful(session: AsyncSession) -> None:
    candidate_id, answer_id = await _seed(session)
    answer = await process_answer(
        session,
        answer_id,
        asr_client=FakeASR(),
        llm_client=FakeLLM(),
        storage=FakeStorage({}),  # аудио нет -> ошибка транскрибации
    )
    assert answer is not None
    assert answer.processing_status == AnswerProcessingStatus.ERROR
    assessment = await _assessment(session, candidate_id)
    assert assessment.system_status == AssessmentStatus.NEEDS_CHECK
    assert await session.get(InterviewResult, candidate_id) is not None


def test_pipeline_task_registered() -> None:
    from app.celery_app import celery_app

    assert "app.process_answer" in celery_app.tasks
