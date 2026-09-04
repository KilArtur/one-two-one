"""Topic assessment service tests (TASK-016 / M6, Р13 + Р16 + Р21)."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

import pytest
from sqlalchemy import select

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
    SkillType,
    Topic,
    TopicAssessment,
    TopicStatus,
    Vacancy,
    VacancyGrade,
    VacancyStatus,
)
from app.prompts import load_prompt
from app.services.topic_assessment import (
    AssessTopicResult,
    TopicAssessmentError,
    _EvidenceDraft,
    _SignalsDraft,
    _TopicAssessmentLLMOutput,
    assess_topic,
)


class _FakeLLM:
    """LLMClient stand-in that returns canned assessment output."""

    def __init__(
        self,
        *,
        output: _TopicAssessmentLLMOutput | None = None,
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
        schema: type[_TopicAssessmentLLMOutput],
        *,
        prompt_version: str,
        role: Any = None,
        system: str | None = None,
    ) -> LLMResult[_TopicAssessmentLLMOutput]:
        self.calls += 1
        self.last_prompt = prompt
        self.last_system = system
        if self.fail:
            raise LLMError("simulated network failure")
        assert schema is _TopicAssessmentLLMOutput
        assert system
        assert prompt_version
        assert self.output is not None
        return LLMResult(
            content=self.output,
            model_version="test-model",
            prompt_version=prompt_version,
        )


def _confirmed_output(*, quote: str, timecode_sec: float) -> _TopicAssessmentLLMOutput:
    return _TopicAssessmentLLMOutput(
        signals=_SignalsDraft(
            correctness=True,
            example=True,
            personal_contribution=True,
        ),
        confidence=Confidence.HIGH,
        no_experience=False,
        evidence=[_EvidenceDraft(quote=quote, timecode_sec=timecode_sec)],
        reasoning_summary="Solid Kafka example with personal ownership",
    )


async def _seed(
    session: Any,
    *,
    topic_title: str = "Kafka",
    requirement: str = "Operate Kafka in production",
) -> tuple[Vacancy, Topic, Candidate, Question, Answer]:
    vacancy = Vacancy(
        id=uuid.uuid4(),
        title="Backend Engineer",
        grade=VacancyGrade.MIDDLE,
        tasks="Build APIs",
        specialist_profile="Python",
        version=1,
        status=VacancyStatus.ACTIVE,
    )
    topic = Topic(
        id=uuid.uuid4(),
        vacancy_id=vacancy.id,
        title=topic_title,
        skill_type=SkillType.HARD,
        importance=Importance.MANDATORY,
        requirement_description=requirement,
        depth_expectations="Partitions, consumer groups",
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
        text=f"Tell about your experience with {topic_title}",
        source_reason="Checks production experience",
    )
    session.add_all([vacancy, topic, candidate, question])
    await session.flush()
    return vacancy, topic, candidate, question, Answer(
        id=uuid.uuid4(),
        question_id=question.id,
        transcript="",
        transcript_segments=[],
        processing_status=ProcessingStatus.READY,
    )


async def _cleanup(
    session: Any,
    *,
    vacancy_id: uuid.UUID,
    topic_id: uuid.UUID,
    candidate_id: uuid.UUID,
    question_id: uuid.UUID,
    answer_id: uuid.UUID,
) -> None:
    from sqlalchemy import text

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


@pytest.mark.asyncio
async def test_assess_topic_confirmed_with_evidence_timecode() -> None:
    """Шаг 1: ответ с примером -> confirmed + цитата с таймкодом."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    quote = "I ran Kafka in production and owned consumer lag alerts"
    timecode = 1.0
    fake = _FakeLLM(output=_confirmed_output(quote=quote, timecode_sec=timecode))

    async with AsyncSessionLocal() as session:
        vacancy, topic, candidate, question, answer = await _seed(session)
        answer.transcript = (
            f"{quote}. We also used Redis for caching, but that is unrelated."
        )
        answer.transcript_segments = [
            {"start": timecode, "end": 4.5, "text": quote},
            {
                "start": 5.0,
                "end": 7.0,
                "text": "We also used Redis for caching, but that is unrelated.",
            },
        ]
        session.add(answer)
        await session.commit()

        result = await assess_topic(
            session,
            candidate_id=candidate.id,
            topic=topic,
            question=question,
            answer=answer,
            llm=fake,  # type: ignore[arg-type]
        )

        assert isinstance(result, AssessTopicResult)
        assert result.created is True
        assert fake.calls == 1
        assert result.assessment.system_status == TopicStatus.CONFIRMED
        assert result.assessment.current_status == TopicStatus.CONFIRMED
        assert result.assessment.signals == {
            "correctness": True,
            "example": True,
            "personal_contribution": True,
        }
        assert len(result.evidence) == 1
        assert result.evidence[0]["quote"] == quote
        assert result.evidence[0]["timecode_sec"] == timecode
        assert result.evidence[0]["question_id"] == str(question.id)
        assert result.model_version == "test-model"
        assert result.prompt_version == load_prompt("assess_topic").version

        await _cleanup(
            session,
            vacancy_id=vacancy.id,
            topic_id=topic.id,
            candidate_id=candidate.id,
            question_id=question.id,
            answer_id=answer.id,
        )


@pytest.mark.asyncio
async def test_foreign_technology_does_not_affect_status() -> None:
    """Шаг 2: упоминание чужой технологии не влияет на статус (Р16)."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    quote = "I configured Kafka partitions and consumer groups myself"
    # LLM (stub) evaluates Kafka only; Redis mention must not appear in evidence.
    fake = _FakeLLM(output=_confirmed_output(quote=quote, timecode_sec=2.0))

    async with AsyncSessionLocal() as session:
        vacancy, topic, candidate, question, answer = await _seed(
            session,
            topic_title="Kafka",
            requirement="Kafka operations experience",
        )
        answer.transcript = (
            f"{quote}. I also know Redis and Kubernetes very well."
        )
        answer.transcript_segments = [
            {"start": 2.0, "end": 5.0, "text": quote},
            {
                "start": 5.5,
                "end": 8.0,
                "text": "I also know Redis and Kubernetes very well.",
            },
        ]
        session.add(answer)
        await session.commit()

        result = await assess_topic(
            session,
            candidate_id=candidate.id,
            topic=topic,
            question=question,
            answer=answer,
            llm=fake,  # type: ignore[arg-type]
        )

        assert result.assessment.system_status == TopicStatus.CONFIRMED
        assert fake.last_system is not None
        assert "R16" in fake.last_system or "ignored" in fake.last_system.lower()
        assert fake.last_prompt is not None
        assert "Ignore mentions of technologies outside" in fake.last_prompt
        # User prompt carries only this topic's requirement (not Redis/K8s topics).
        match = re.search(r"\{[\s\S]*\}\s*$", fake.last_prompt)
        assert match is not None
        payload = json.loads(match.group(0))
        assert payload["topic"]["title"] == "Kafka"
        assert "Redis" not in payload["topic"]["requirement_description"]
        assert "Kubernetes" not in payload["topic"]["requirement_description"]
        # Evidence is about Kafka only.
        assert all("Redis" not in e["quote"] for e in result.evidence)
        assert all("Kubernetes" not in e["quote"] for e in result.evidence)
        assert all(e["question_id"] == str(question.id) for e in result.evidence)

        await _cleanup(
            session,
            vacancy_id=vacancy.id,
            topic_id=topic.id,
            candidate_id=candidate.id,
            question_id=question.id,
            answer_id=answer.id,
        )


@pytest.mark.asyncio
async def test_system_status_fixed_separately_from_current() -> None:
    """Шаг 3: system_status зафиксирован отдельно от current_status (Р21)."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    quote = "I tuned Kafka throughput with compression and batching"
    fake = _FakeLLM(output=_confirmed_output(quote=quote, timecode_sec=0.5))

    async with AsyncSessionLocal() as session:
        vacancy, topic, candidate, question, answer = await _seed(session)
        vacancy_id = vacancy.id
        topic_id = topic.id
        candidate_id = candidate.id
        question_id = question.id
        answer_id = answer.id
        answer.transcript = quote
        answer.transcript_segments = [
            {"start": 0.5, "end": 3.0, "text": quote},
        ]
        session.add(answer)
        await session.commit()

        first = await assess_topic(
            session,
            candidate_id=candidate_id,
            topic=topic,
            question=question,
            answer=answer,
            llm=fake,  # type: ignore[arg-type]
        )
        assert first.created is True
        assert first.assessment.system_status == TopicStatus.CONFIRMED
        assert first.assessment.current_status == TopicStatus.CONFIRMED
        assessment_id = first.assessment.id

        # Expert changes only current_status.
        loaded = await session.get(TopicAssessment, assessment_id)
        assert loaded is not None
        loaded.current_status = TopicStatus.NEEDS_CHECK
        await session.commit()
        await session.refresh(loaded)
        assert loaded.system_status == TopicStatus.CONFIRMED
        assert loaded.current_status == TopicStatus.NEEDS_CHECK

        # Re-assess is idempotent: no LLM call, system_status untouched.
        second = await assess_topic(
            session,
            candidate_id=candidate_id,
            topic=topic,
            question=question,
            answer=answer,
            llm=fake,  # type: ignore[arg-type]
        )
        assert second.created is False
        assert fake.calls == 1
        assert second.assessment.system_status == TopicStatus.CONFIRMED
        assert second.assessment.current_status == TopicStatus.NEEDS_CHECK

        # Direct overwrite of system_status is rejected by ORM guard.
        loaded2 = await session.get(TopicAssessment, assessment_id)
        assert loaded2 is not None
        loaded2.system_status = TopicStatus.NOT_CONFIRMED
        with pytest.raises(RuntimeError, match="system_status is immutable"):
            await session.commit()
        await session.rollback()

        again = await session.get(TopicAssessment, assessment_id)
        assert again is not None
        assert again.system_status == TopicStatus.CONFIRMED

        await _cleanup(
            session,
            vacancy_id=vacancy_id,
            topic_id=topic_id,
            candidate_id=candidate_id,
            question_id=question_id,
            answer_id=answer_id,
        )


@pytest.mark.asyncio
async def test_skipped_answer_not_confirmed_without_llm() -> None:
    """Conscious skip → not_confirmed, no LLM call."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    fake = _FakeLLM(output=_confirmed_output(quote="unused", timecode_sec=0.0))

    async with AsyncSessionLocal() as session:
        vacancy, topic, candidate, question, answer = await _seed(session)
        answer.skipped = True
        session.add(answer)
        await session.commit()

        result = await assess_topic(
            session,
            candidate_id=candidate.id,
            topic=topic,
            question=question,
            answer=answer,
            llm=fake,  # type: ignore[arg-type]
        )
        assert result.created is True
        assert fake.calls == 0
        assert result.assessment.system_status == TopicStatus.NOT_CONFIRMED
        assert result.evidence == []

        await _cleanup(
            session,
            vacancy_id=vacancy.id,
            topic_id=topic.id,
            candidate_id=candidate.id,
            question_id=question.id,
            answer_id=answer.id,
        )


@pytest.mark.asyncio
async def test_llm_failure_raises_and_persists_nothing() -> None:
    """On LLM failure nothing is written for this candidate/topic."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    fake = _FakeLLM(fail=True)

    async with AsyncSessionLocal() as session:
        vacancy, topic, candidate, question, answer = await _seed(session)
        answer.transcript = "Some answer"
        answer.transcript_segments = [
            {"start": 0.0, "end": 1.0, "text": "Some answer"},
        ]
        session.add(answer)
        await session.commit()

        with pytest.raises(TopicAssessmentError, match="LLM call failed"):
            await assess_topic(
                session,
                candidate_id=candidate.id,
                topic=topic,
                question=question,
                answer=answer,
                llm=fake,  # type: ignore[arg-type]
            )

        found = await session.execute(
            select(TopicAssessment).where(
                TopicAssessment.candidate_id == candidate.id,
                TopicAssessment.topic_id == topic.id,
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
