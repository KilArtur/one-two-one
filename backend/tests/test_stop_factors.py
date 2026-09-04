"""Stop-factor assessment tests (TASK-017 / M6, Р6)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select, text

from app.config import get_settings
from app.integrations.llm import LLMError, LLMResult
from app.models import (
    Answer,
    Candidate,
    CandidateStatus,
    Confidence,
    Importance,
    ProcessingStatus,
    Question,
    QuestionPattern,
    QuestionType,
    Recommendation,
    SkillType,
    StopFactorFlag,
    Topic,
    TopicAssessment,
    Vacancy,
    VacancyGrade,
    VacancyStatus,
)
from app.prompts import load_prompt
from app.services.stop_factors import (
    AssessStopFactorsResult,
    StopFactorAssessmentError,
    _EvidenceDraft,
    _FactorDraft,
    _StopFactorsLLMOutput,
    assess_stop_factors,
    recommendation_with_stop_factor,
    resolve_stop_factor_trigger,
)


class _FakeLLM:
    """LLMClient stand-in for stop-factor structured output."""

    def __init__(
        self,
        *,
        output: _StopFactorsLLMOutput | None = None,
        fail: bool = False,
    ) -> None:
        self.output = output
        self.fail = fail
        self.calls = 0
        self.last_prompt: str | None = None
        self.last_system: str | None = None

    async def acomplete_structured(
        self,
        prompt: str,
        schema: type[_StopFactorsLLMOutput],
        *,
        prompt_version: str,
        role: Any = None,
        system: str | None = None,
    ) -> LLMResult[_StopFactorsLLMOutput]:
        self.calls += 1
        self.last_prompt = prompt
        self.last_system = system
        if self.fail:
            raise LLMError("simulated network failure")
        assert schema is _StopFactorsLLMOutput
        assert system
        assert prompt_version
        assert self.output is not None
        return LLMResult(
            content=self.output,
            model_version="test-model",
            prompt_version=prompt_version,
        )


def _explicit_trigger_output(
    *,
    stop_factor: str,
    quote: str,
    timecode_sec: float,
    answer_id: uuid.UUID,
) -> _StopFactorsLLMOutput:
    return _StopFactorsLLMOutput(
        factors=[
            _FactorDraft(
                stop_factor=stop_factor,
                triggered=True,
                confidence=Confidence.HIGH,
                evidence=[
                    _EvidenceDraft(
                        quote=quote,
                        timecode_sec=timecode_sec,
                        answer_id=str(answer_id),
                    )
                ],
                reasoning_summary="Explicit unambiguous statement matching stop-factor",
            )
        ]
    )


def _vague_output(*, stop_factor: str) -> _StopFactorsLLMOutput:
    return _StopFactorsLLMOutput(
        factors=[
            _FactorDraft(
                stop_factor=stop_factor,
                triggered=False,
                confidence=Confidence.LOW,
                evidence=[],
                reasoning_summary="Answer is evasive; leave for human review",
            )
        ]
    )


async def _seed(
    session: Any,
    *,
    stop_factors: list[str],
) -> tuple[Vacancy, Topic, Candidate, Question, Answer]:
    vacancy = Vacancy(
        id=uuid.uuid4(),
        title="Backend Engineer",
        grade=VacancyGrade.MIDDLE,
        tasks="Build APIs",
        stop_factors=list(stop_factors),
        specialist_profile="Python",
        version=1,
        status=VacancyStatus.ACTIVE,
    )
    topic = Topic(
        id=uuid.uuid4(),
        vacancy_id=vacancy.id,
        title="Relocation",
        skill_type=SkillType.SOFT,
        importance=Importance.MANDATORY,
        requirement_description="Willingness to relocate",
        depth_expectations="Clear yes/no with constraints",
        order=1,
    )
    candidate = Candidate(
        id=uuid.uuid4(),
        vacancy_id=vacancy.id,
        resume_text="Python developer",
        status=CandidateStatus.SUBMITTED,
    )
    question = Question(
        id=uuid.uuid4(),
        topic_id=topic.id,
        type=QuestionType.CORE,
        pattern=QuestionPattern.EXPERIENCE,
        text="Are you ready to relocate to the office city?",
        source_reason="Checks relocation stop-factor context",
    )
    session.add_all([vacancy, topic, candidate, question])
    await session.flush()
    answer = Answer(
        id=uuid.uuid4(),
        question_id=question.id,
        transcript="",
        transcript_segments=[],
        processing_status=ProcessingStatus.READY,
    )
    return vacancy, topic, candidate, question, answer


async def _cleanup(
    session: Any,
    *,
    vacancy_id: uuid.UUID,
    topic_id: uuid.UUID,
    candidate_id: uuid.UUID,
    question_id: uuid.UUID,
    answer_id: uuid.UUID,
) -> None:
    await session.execute(
        text("DELETE FROM stop_factor_flag WHERE candidate_id = :id"),
        {"id": candidate_id},
    )
    await session.execute(
        text(
            "DELETE FROM status_change_log WHERE assessment_id IN "
            "(SELECT id FROM topic_assessment WHERE candidate_id = :id)"
        ),
        {"id": candidate_id},
    )
    await session.execute(
        text("DELETE FROM topic_assessment WHERE candidate_id = :id"),
        {"id": candidate_id},
    )
    await session.execute(
        text("DELETE FROM answer WHERE id = :id"),
        {"id": answer_id},
    )
    await session.execute(
        text("DELETE FROM question WHERE id = :id"),
        {"id": question_id},
    )
    await session.execute(
        text("DELETE FROM candidate WHERE id = :id"),
        {"id": candidate_id},
    )
    await session.execute(
        text("DELETE FROM topic WHERE id = :id"),
        {"id": topic_id},
    )
    await session.execute(
        text("DELETE FROM vacancy WHERE id = :id"),
        {"id": vacancy_id},
    )
    await session.commit()


def test_resolve_stop_factor_trigger_requires_high_confidence_and_evidence() -> None:
    """Р6 gate is deterministic: medium/low or no quote → no auto-trigger."""
    assert (
        resolve_stop_factor_trigger(
            llm_triggered=True,
            confidence=Confidence.HIGH,
            evidence=[{"quote": "x", "timecode_sec": 1.0}],
        )
        is True
    )
    assert (
        resolve_stop_factor_trigger(
            llm_triggered=True,
            confidence=Confidence.MEDIUM,
            evidence=[{"quote": "x", "timecode_sec": 1.0}],
        )
        is False
    )
    assert (
        resolve_stop_factor_trigger(
            llm_triggered=True,
            confidence=Confidence.LOW,
            evidence=[{"quote": "x", "timecode_sec": 1.0}],
        )
        is False
    )
    assert (
        resolve_stop_factor_trigger(
            llm_triggered=True,
            confidence=Confidence.HIGH,
            evidence=[],
        )
        is False
    )
    assert (
        resolve_stop_factor_trigger(
            llm_triggered=False,
            confidence=Confidence.HIGH,
            evidence=[{"quote": "x", "timecode_sec": 1.0}],
        )
        is False
    )


def test_recommendation_with_stop_factor() -> None:
    """Triggered stop-factor → not_suitable; otherwise human path."""
    assert (
        recommendation_with_stop_factor(triggered=True)
        is Recommendation.NOT_SUITABLE
    )
    assert (
        recommendation_with_stop_factor(triggered=False)
        is Recommendation.NEEDS_ADDITIONAL_CHECK
    )


@pytest.mark.asyncio
async def test_explicit_stop_answer_sets_recommendation_not_suitable() -> None:
    """Шаг 1: явный стоп-ответ — recommendation учитывает стоп-фактор."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    stop_text = "не готов к релокации"
    quote = "Я категорически не готов переезжать в другой город"
    timecode = 2.5

    async with AsyncSessionLocal() as session:
        vacancy, topic, candidate, question, answer = await _seed(
            session,
            stop_factors=[stop_text],
        )
        answer.transcript = quote
        answer.transcript_segments = [
            {"start": timecode, "end": 6.0, "text": quote},
        ]
        session.add(answer)
        await session.commit()

        fake = _FakeLLM(
            output=_explicit_trigger_output(
                stop_factor=stop_text,
                quote=quote,
                timecode_sec=timecode,
                answer_id=answer.id,
            )
        )
        result = await assess_stop_factors(
            session,
            candidate_id=candidate.id,
            stop_factors=list(vacancy.stop_factors),
            answers=[(answer, question)],
            llm=fake,  # type: ignore[arg-type]
        )

        assert isinstance(result, AssessStopFactorsResult)
        assert result.created is True
        assert fake.calls == 1
        assert result.triggered is True
        assert result.recommendation is Recommendation.NOT_SUITABLE
        assert result.flag.triggered is True
        assert result.flag.candidate_id == candidate.id

        # Flag is stored separately from topic assessments.
        assessments = await session.execute(
            select(TopicAssessment).where(
                TopicAssessment.candidate_id == candidate.id
            )
        )
        assert assessments.scalars().all() == []
        flag_row = await session.get(StopFactorFlag, candidate.id)
        assert flag_row is not None
        assert flag_row.triggered is True

        await _cleanup(
            session,
            vacancy_id=vacancy.id,
            topic_id=topic.id,
            candidate_id=candidate.id,
            question_id=question.id,
            answer_id=answer.id,
        )


@pytest.mark.asyncio
async def test_vague_answer_does_not_trigger_stop_factor() -> None:
    """Шаг 2: размытый ответ — стоп-фактор не срабатывает."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    stop_text = "не готов к релокации"
    vague = "Ну, посмотрим по обстоятельствам, сложно сказать сейчас"

    async with AsyncSessionLocal() as session:
        vacancy, topic, candidate, question, answer = await _seed(
            session,
            stop_factors=[stop_text],
        )
        answer.transcript = vague
        answer.transcript_segments = [
            {"start": 0.0, "end": 3.0, "text": vague},
        ]
        session.add(answer)
        await session.commit()

        fake = _FakeLLM(output=_vague_output(stop_factor=stop_text))
        result = await assess_stop_factors(
            session,
            candidate_id=candidate.id,
            stop_factors=list(vacancy.stop_factors),
            answers=[(answer, question)],
            llm=fake,  # type: ignore[arg-type]
        )

        assert result.triggered is False
        assert result.flag.triggered is False
        assert result.recommendation is Recommendation.NEEDS_ADDITIONAL_CHECK
        assert result.evidence == []
        assert fake.last_system is not None
        assert "R6" in fake.last_system or "evasive" in fake.last_system.lower()

        await _cleanup(
            session,
            vacancy_id=vacancy.id,
            topic_id=topic.id,
            candidate_id=candidate.id,
            question_id=question.id,
            answer_id=answer.id,
        )


@pytest.mark.asyncio
async def test_triggered_stop_factor_has_evidence_with_timecode() -> None:
    """Шаг 3: проверить наличие evidence с таймкодом."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    stop_text = "нет опыта коммерческой разработки"
    quote = "У меня совсем нет коммерческого опыта разработки"
    timecode = 1.25

    async with AsyncSessionLocal() as session:
        vacancy, topic, candidate, question, answer = await _seed(
            session,
            stop_factors=[stop_text],
        )
        answer.transcript = quote
        answer.transcript_segments = [
            {"start": timecode, "end": 4.0, "text": quote},
        ]
        session.add(answer)
        await session.commit()

        fake = _FakeLLM(
            output=_explicit_trigger_output(
                stop_factor=stop_text,
                quote=quote,
                timecode_sec=timecode,
                answer_id=answer.id,
            )
        )
        result = await assess_stop_factors(
            session,
            candidate_id=candidate.id,
            stop_factors=list(vacancy.stop_factors),
            answers=[(answer, question)],
            llm=fake,  # type: ignore[arg-type]
        )

        assert result.triggered is True
        assert len(result.evidence) >= 1
        assert result.evidence[0]["quote"] == quote
        assert result.evidence[0]["timecode_sec"] == timecode
        assert result.evidence[0]["answer_id"] == str(answer.id)
        assert result.evidence[0]["stop_factor"] == stop_text
        assert result.flag.evidence[0]["timecode_sec"] == timecode
        assert result.prompt_version == load_prompt("assess_stop_factors").version
        assert result.model_version == "test-model"

        # Idempotent re-run does not call LLM again.
        again = await assess_stop_factors(
            session,
            candidate_id=candidate.id,
            stop_factors=list(vacancy.stop_factors),
            answers=[(answer, question)],
            llm=fake,  # type: ignore[arg-type]
        )
        assert again.created is False
        assert fake.calls == 1
        assert again.triggered is True

        await _cleanup(
            session,
            vacancy_id=vacancy.id,
            topic_id=topic.id,
            candidate_id=candidate.id,
            question_id=question.id,
            answer_id=answer.id,
        )


@pytest.mark.asyncio
async def test_llm_failure_persists_nothing() -> None:
    """On LLM failure no stop_factor_flag row is written."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        vacancy, topic, candidate, question, answer = await _seed(
            session,
            stop_factors=["не готов к релокации"],
        )
        answer.transcript = "Some answer"
        answer.transcript_segments = [
            {"start": 0.0, "end": 1.0, "text": "Some answer"},
        ]
        session.add(answer)
        await session.commit()

        with pytest.raises(StopFactorAssessmentError, match="LLM call failed"):
            await assess_stop_factors(
                session,
                candidate_id=candidate.id,
                stop_factors=list(vacancy.stop_factors),
                answers=[(answer, question)],
                llm=_FakeLLM(fail=True),  # type: ignore[arg-type]
            )

        found = await session.execute(
            select(StopFactorFlag).where(
                StopFactorFlag.candidate_id == candidate.id
            )
        )
        assert found.scalar_one_or_none() is None

        await _cleanup(
            session,
            vacancy_id=vacancy.id,
            topic_id=topic.id,
            candidate_id=candidate.id,
            question_id=question.id,
            answer_id=answer.id,
        )
