"""Оценка стоп-факторов Р6: авто «не подходит» только при явном ответе с high confidence."""

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
from app.models.topic_assessment import AssessmentConfidence
from app.models.vacancy import Vacancy, VacancyGrade
from app.schemas.assessment import StopFactorLLM
from app.services.stop_factor import (
    candidate_stop_factor_triggered,
    evaluate_stop_factor,
    resolve_stop_factor,
)

STOP_FACTOR = "Не готов к работе из офиса 5 дней в неделю"


class FakeLLM:
    def __init__(self, verdict: StopFactorLLM) -> None:
        self.calls = 0
        self.verdict = verdict

    async def generate_structured(
        self, prompt: object, *, schema: type, prompt_version: str, use_fast_model: bool = False
    ) -> LLMInvocationResult[StopFactorLLM]:
        self.calls += 1
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


async def _seed(session: AsyncSession, segments: list[dict]) -> tuple[uuid.UUID, uuid.UUID]:
    vacancy = Vacancy(
        id=uuid.uuid4(), title="Backend", grade=VacancyGrade.MIDDLE, stop_factors=[STOP_FACTOR]
    )
    vacancy.lineage_id = vacancy.id
    topic = Topic(
        vacancy_id=vacancy.id,
        title="Формат работы",
        skill_type=SkillType.SOFT,
        importance=TopicImportance.MANDATORY,
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
        text="Готовы ли вы работать из офиса 5 дней в неделю?",
    )
    session.add(question)
    await session.flush()
    answer = Answer(
        question_id=question.id,
        transcript="; ".join(s["text"] for s in segments),
        transcript_segments=segments,
    )
    session.add(answer)
    await session.commit()
    return candidate.id, answer.id


def test_resolve_stop_factor_rule() -> None:
    # срабатывает только при явном ответе + high + наличии evidence
    assert resolve_stop_factor(
        triggered_explicitly=True, confidence=AssessmentConfidence.HIGH, has_evidence=True
    )
    assert not resolve_stop_factor(
        triggered_explicitly=False, confidence=AssessmentConfidence.HIGH, has_evidence=True
    )
    assert not resolve_stop_factor(
        triggered_explicitly=True, confidence=AssessmentConfidence.MEDIUM, has_evidence=True
    )
    assert not resolve_stop_factor(
        triggered_explicitly=True, confidence=AssessmentConfidence.HIGH, has_evidence=False
    )


@pytest.mark.anyio
async def test_explicit_answer_triggers_with_evidence(session: AsyncSession) -> None:
    segments = [{"text": "нет, из офиса каждый день я работать не готов", "start": 2.0, "end": 6.0}]
    candidate_id, answer_id = await _seed(session, segments)
    fake = FakeLLM(
        StopFactorLLM(
            triggered_explicitly=True,
            confidence=AssessmentConfidence.HIGH,
            evidence_quote="из офиса каждый день я работать не готов",
            reasoning_summary="прямой отказ",
        )
    )

    flag = await evaluate_stop_factor(
        session, candidate_id, answer_id, STOP_FACTOR, llm_client=fake
    )

    assert flag is not None
    assert flag.triggered is True
    assert flag.evidence is not None
    assert flag.evidence["start_sec"] == 2.0 and flag.evidence["end_sec"] == 6.0
    assert flag.evidence["question_id"]
    # Шаг 1: рекомендация (Р5) учтёт сработавший стоп-фактор
    assert await candidate_stop_factor_triggered(session, candidate_id) is True


@pytest.mark.anyio
async def test_evasive_answer_not_triggered(session: AsyncSession) -> None:
    segments = [
        {"text": "ну, наверное, можно обсудить, зависит от условий", "start": 1.0, "end": 4.0}
    ]
    candidate_id, answer_id = await _seed(session, segments)
    fake = FakeLLM(
        StopFactorLLM(
            triggered_explicitly=False,
            confidence=AssessmentConfidence.LOW,
            evidence_quote="",
            reasoning_summary="уклончивый ответ",
        )
    )

    flag = await evaluate_stop_factor(
        session, candidate_id, answer_id, STOP_FACTOR, llm_client=fake
    )

    assert flag is not None
    assert flag.triggered is False
    # Шаг 2: уклончивый ответ не срабатывает — уходит человеку
    assert await candidate_stop_factor_triggered(session, candidate_id) is False


@pytest.mark.anyio
async def test_explicit_but_medium_confidence_not_triggered(session: AsyncSession) -> None:
    segments = [{"text": "скорее нет", "start": 0.0, "end": 1.5}]
    candidate_id, answer_id = await _seed(session, segments)
    fake = FakeLLM(
        StopFactorLLM(
            triggered_explicitly=True,
            confidence=AssessmentConfidence.MEDIUM,
            evidence_quote="скорее нет",
            reasoning_summary="неоднозначно",
        )
    )

    flag = await evaluate_stop_factor(
        session, candidate_id, answer_id, STOP_FACTOR, llm_client=fake
    )

    assert flag is not None
    assert flag.triggered is False
