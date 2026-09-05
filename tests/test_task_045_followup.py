"""Адаптивные уточняющие вопросы M4/Р12 на LangGraph (TASK-045)."""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.integrations.llm import LLMClientError, LLMInvocationResult
from app.models.answer import Answer, AnswerProcessingStatus
from app.models.candidate import Candidate
from app.models.question import Question, QuestionPattern, QuestionType
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.vacancy import Vacancy, VacancyGrade
from app.schemas.assessment import FollowupDecisionLLM
from app.services.followup import decide_followup


class FakeLLM:
    def __init__(self, verdict: FollowupDecisionLLM | None = None, error: Exception | None = None):
        self.verdict = verdict
        self.error = error
        self.calls = 0

    async def generate_structured(self, prompt, *, schema, prompt_version, use_fast_model=False):
        self.calls += 1
        assert use_fast_model is True  # горячий путь Р12 — быстрая модель
        if self.error is not None:
            raise self.error
        return LLMInvocationResult(
            content=self.verdict, model_version="fast", prompt_version=prompt_version
        )


def _verdict(**kw) -> FollowupDecisionLLM:
    base = dict(
        answer_sufficient=False,
        explicit_no_experience=False,
        adds_new_information=True,
        needs_clarification=True,
        followup_question="Приведите конкретный пример из вашего проекта.",
    )
    base.update(kw)
    return FollowupDecisionLLM(**base)


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


async def _seed(
    session: AsyncSession, *, followups: int = 0
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    vacancy = Vacancy(id=uuid.uuid4(), title="Backend", grade=VacancyGrade.MIDDLE)
    vacancy.lineage_id = vacancy.id
    topic = Topic(
        vacancy_id=vacancy.id,
        title="PostgreSQL",
        skill_type=SkillType.HARD,
        importance=TopicImportance.MANDATORY,
        requirement_description="Индексы, схема",
        order=0,
    )
    vacancy.topics = [topic]
    candidate = Candidate(vacancy_id=vacancy.id)
    session.add_all([vacancy, candidate])
    await session.flush()
    core = Question(
        topic_id=topic.id, type=QuestionType.CORE, pattern=QuestionPattern.EXPERIENCE, text="Core?"
    )
    session.add(core)
    await session.flush()
    session.add(
        Answer(
            candidate_id=candidate.id,
            question_id=core.id,
            transcript="Работал с базами",
            processing_status=AnswerProcessingStatus.READY,
        )
    )
    for i in range(followups):
        fu = Question(
            candidate_id=candidate.id,
            topic_id=topic.id,
            type=QuestionType.FOLLOW_UP,
            pattern=QuestionPattern.REASONING,
            text=f"FU{i}",
            parent_question_id=core.id,
        )
        session.add(fu)
        await session.flush()
        session.add(
            Answer(
                candidate_id=candidate.id,
                question_id=fu.id,
                transcript=f"уточнение {i}",
                processing_status=AnswerProcessingStatus.READY,
            )
        )
    await session.commit()
    return candidate.id, topic.id, core.id


async def _followup_count(session, topic_id) -> int:
    return await session.scalar(
        select(func.count())
        .select_from(Question)
        .where(Question.topic_id == topic_id, Question.type == QuestionType.FOLLOW_UP)
    )


@pytest.mark.anyio
async def test_general_answer_gets_followup(session: AsyncSession) -> None:
    candidate_id, topic_id, _ = await _seed(session)
    result = await decide_followup(session, candidate_id, topic_id, llm_client=FakeLLM(_verdict()))

    assert result.ask is True
    assert result.question is not None
    assert result.question.type == QuestionType.FOLLOW_UP
    assert await _followup_count(session, topic_id) == 1


@pytest.mark.anyio
async def test_no_experience_no_followup(session: AsyncSession) -> None:
    candidate_id, topic_id, _ = await _seed(session)
    result = await decide_followup(
        session,
        candidate_id,
        topic_id,
        llm_client=FakeLLM(_verdict(explicit_no_experience=True)),
    )
    assert result.ask is False
    assert result.reason == "no_experience"
    assert await _followup_count(session, topic_id) == 0


@pytest.mark.anyio
async def test_status_determined_no_followup(session: AsyncSession) -> None:
    candidate_id, topic_id, _ = await _seed(session)
    result = await decide_followup(
        session, candidate_id, topic_id, llm_client=FakeLLM(_verdict(answer_sufficient=True))
    )
    assert result.ask is False
    assert result.reason == "status_determined"


@pytest.mark.anyio
async def test_limit_two_followups_stops(session: AsyncSession) -> None:
    candidate_id, topic_id, _ = await _seed(session, followups=2)
    fake = FakeLLM(_verdict())
    result = await decide_followup(session, candidate_id, topic_id, llm_client=fake)

    assert result.ask is False
    assert result.reason == "limit_reached"
    assert fake.calls == 0  # гейт лимита сработал до LLM
    assert await _followup_count(session, topic_id) == 2


@pytest.mark.anyio
async def test_no_new_information_stops(session: AsyncSession) -> None:
    candidate_id, topic_id, _ = await _seed(session, followups=1)
    result = await decide_followup(
        session,
        candidate_id,
        topic_id,
        llm_client=FakeLLM(_verdict(adds_new_information=False)),
    )
    assert result.ask is False
    assert result.reason == "no_new_information"


@pytest.mark.anyio
async def test_llm_failure_closes_topic(session: AsyncSession) -> None:
    candidate_id, topic_id, _ = await _seed(session)
    result = await decide_followup(
        session,
        candidate_id,
        topic_id,
        llm_client=FakeLLM(error=LLMClientError("x", "m", "p", "u")),
    )
    assert result.ask is False
    assert result.reason == "llm_error"
    assert await _followup_count(session, topic_id) == 0


@pytest.mark.anyio
async def test_followup_continues_the_personalized_question(session: AsyncSession) -> None:
    candidate_id, topic_id, core_id = await _seed(session)
    personal = Question(
        candidate_id=candidate_id,
        topic_id=topic_id,
        type=QuestionType.PERSONAL,
        pattern=QuestionPattern.EXPERIENCE,
        text="Личный вопрос по резюме",
        parent_question_id=core_id,
    )
    session.add(personal)
    await session.flush()
    session.add(
        Answer(
            candidate_id=candidate_id,
            question_id=personal.id,
            transcript="Отвечал про свой проект",
            processing_status=AnswerProcessingStatus.READY,
        )
    )
    await session.commit()

    result = await decide_followup(session, candidate_id, topic_id, llm_client=FakeLLM(_verdict()))

    assert result.ask is True
    assert result.question.type == QuestionType.FOLLOW_UP
    assert result.question.parent_question_id == personal.id


@pytest.mark.anyio
async def test_followups_are_candidate_scoped_and_retry_is_idempotent(
    session: AsyncSession,
) -> None:
    candidate_id, topic_id, core_id = await _seed(session)
    first = await decide_followup(session, candidate_id, topic_id, llm_client=FakeLLM(_verdict()))
    retry = await decide_followup(session, candidate_id, topic_id, llm_client=FakeLLM(_verdict()))
    assert first.question.id == retry.question.id
    topic = await session.get(Topic, topic_id)
    other = Candidate(vacancy_id=topic.vacancy_id)
    session.add(other)
    await session.flush()
    session.add(Answer(candidate_id=other.id, question_id=core_id, transcript="Общий ответ"))
    await session.commit()
    second = await decide_followup(session, other.id, topic_id, llm_client=FakeLLM(_verdict()))
    assert second.question.id != first.question.id
    assert second.question.candidate_id == other.id
    assert first.question.candidate_id == candidate_id
