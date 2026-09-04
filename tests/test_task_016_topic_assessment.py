"""LLM-оценка топика из транскрипта с evidence и изоляцией Р16 (TASK-016)."""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.integrations.llm import LLMInvocationResult
from app.models.answer import Answer
from app.models.candidate import Candidate
from app.models.question import Question, QuestionPattern, QuestionType
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.topic_assessment import AssessmentConfidence, AssessmentStatus
from app.models.vacancy import Vacancy, VacancyGrade
from app.schemas.assessment import TopicAssessmentLLM
from app.services.topic_assessment import assess_topic


class FakeLLM:
    """LLM-заглушка: фиксированный вердикт, запоминает последний промпт."""

    def __init__(self, verdict: TopicAssessmentLLM) -> None:
        self.calls = 0
        self.last_prompt: str | None = None
        self.verdict = verdict

    async def generate_structured(
        self, prompt: object, *, schema: type, prompt_version: str, use_fast_model: bool = False
    ) -> LLMInvocationResult[TopicAssessmentLLM]:
        self.calls += 1
        self.last_prompt = str(prompt)
        return LLMInvocationResult(
            content=self.verdict, model_version="fake", prompt_version=prompt_version
        )


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


async def _seed(
    session: AsyncSession,
    *,
    requirement: str = "Проектирование схемы и индексов в PostgreSQL",
    segments: list[dict] | None = None,
    skipped: bool = False,
) -> tuple[uuid.UUID, uuid.UUID]:
    vacancy = Vacancy(id=uuid.uuid4(), title="Backend", grade=VacancyGrade.MIDDLE)
    vacancy.lineage_id = vacancy.id
    topic = Topic(
        vacancy_id=vacancy.id,
        title="PostgreSQL",
        skill_type=SkillType.HARD,
        importance=TopicImportance.MANDATORY,
        requirement_description=requirement,
        order=0,
    )
    vacancy.topics = [topic]
    candidate = Candidate(vacancy_id=vacancy.id)
    session.add_all([vacancy, candidate])
    await session.flush()
    question = Question(
        topic_id=topic.id,
        type=QuestionType.CORE,
        pattern=QuestionPattern.EXPERIENCE,
        text="Расскажите про проектирование схемы в PostgreSQL",
    )
    session.add(question)
    await session.flush()
    answer = Answer(
        question_id=question.id,
        transcript="; ".join(s["text"] for s in segments) if segments else None,
        transcript_segments=segments,
        skipped=skipped,
    )
    session.add(answer)
    await session.commit()
    return candidate.id, answer.id


def _verdict(**kwargs) -> TopicAssessmentLLM:
    base = {
        "correctness": True,
        "example": True,
        "personal_contribution": True,
        "confidence": AssessmentConfidence.HIGH,
        "explicit_no_experience": False,
        "technical_error": False,
        "evidence_quote": "я проектировал схему с партиционированием",
        "reasoning_summary": "полный ответ с примером",
    }
    base.update(kwargs)
    return TopicAssessmentLLM(**base)


@pytest.mark.anyio
async def test_answer_with_example_confirmed_with_evidence(session: AsyncSession) -> None:
    segments = [
        {"text": "я проектировал схему с партиционированием", "start": 3.0, "end": 8.5},
        {"text": "использовал составные индексы", "start": 8.5, "end": 12.0},
    ]
    candidate_id, answer_id = await _seed(session, segments=segments)
    fake = FakeLLM(_verdict())

    assessment = await assess_topic(session, candidate_id, answer_id, llm_client=fake)

    assert assessment is not None
    assert assessment.system_status == AssessmentStatus.CONFIRMED
    assert assessment.evidence is not None
    item = assessment.evidence[0]
    assert item["quote"] == "я проектировал схему с партиционированием"
    assert item["start_sec"] == 3.0 and item["end_sec"] == 8.5
    assert item["question_id"]


@pytest.mark.anyio
async def test_isolation_prompt_targets_only_this_topic(session: AsyncSession) -> None:
    # ответ упоминает чужую технологию (MongoDB), топик — PostgreSQL
    segments = [
        {
            "text": "в основном я работал с MongoDB, а в PostgreSQL делал индексы",
            "start": 0.0,
            "end": 6.0,
        },
    ]
    candidate_id, answer_id = await _seed(session, segments=segments)
    fake = FakeLLM(_verdict(evidence_quote="в PostgreSQL делал индексы"))

    await assess_topic(session, candidate_id, answer_id, llm_client=fake)

    assert fake.last_prompt is not None
    # промпт несёт директиву изоляции Р16 и требование только целевого топика
    assert "Р16" in fake.last_prompt
    assert "PostgreSQL" in fake.last_prompt
    assert "игнорируй" in fake.last_prompt.lower()


@pytest.mark.anyio
async def test_system_status_fixed_and_not_overwritten(session: AsyncSession) -> None:
    segments = [{"text": "я проектировал схему с партиционированием", "start": 1.0, "end": 5.0}]
    candidate_id, answer_id = await _seed(session, segments=segments)
    fake = FakeLLM(_verdict())

    first = await assess_topic(session, candidate_id, answer_id, llm_client=fake)
    assert first is not None
    assert first.system_status == first.current_status == AssessmentStatus.CONFIRMED

    # эксперт правит текущий статус — system_status трогать нельзя
    first.current_status = AssessmentStatus.NOT_CONFIRMED
    await session.commit()

    # повторный прогон не создаёт новую оценку и не перезаписывает system_status
    again = await assess_topic(session, candidate_id, answer_id, llm_client=fake)
    assert again is not None
    assert again.id == first.id
    assert again.system_status == AssessmentStatus.CONFIRMED
    assert again.current_status == AssessmentStatus.NOT_CONFIRMED
    assert fake.calls == 1


@pytest.mark.anyio
async def test_skipped_answer_not_confirmed_without_llm(session: AsyncSession) -> None:
    candidate_id, answer_id = await _seed(session, segments=None, skipped=True)
    fake = FakeLLM(_verdict())

    assessment = await assess_topic(session, candidate_id, answer_id, llm_client=fake)

    assert assessment is not None
    assert assessment.system_status == AssessmentStatus.NOT_CONFIRMED
    assert assessment.evidence is None
    assert fake.calls == 0


@pytest.mark.anyio
async def test_no_experience_high_confidence_not_confirmed(session: AsyncSession) -> None:
    segments = [{"text": "с PostgreSQL не работал", "start": 0.0, "end": 2.0}]
    candidate_id, answer_id = await _seed(session, segments=segments)
    fake = FakeLLM(
        _verdict(
            correctness=False,
            example=False,
            personal_contribution=False,
            explicit_no_experience=True,
            evidence_quote="с PostgreSQL не работал",
        )
    )

    assessment = await assess_topic(session, candidate_id, answer_id, llm_client=fake)

    assert assessment is not None
    assert assessment.system_status == AssessmentStatus.NOT_CONFIRMED
