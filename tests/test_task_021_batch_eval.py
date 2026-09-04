"""Batch-runner оценки транскриптов без видео (TASK-021)."""

from pathlib import Path

import pytest

from app.integrations.llm import LLMInvocationResult
from app.models.topic_assessment import AssessmentConfidence
from app.schemas.assessment import TopicAssessmentLLM
from app.services.batch_eval import load_input, parse_candidates, run_batch

SAMPLE = Path(__file__).resolve().parents[1] / "scripts" / "batch_eval_sample.json"


class DeterministicLLM:
    """Fake LLM: вердикт зависит от содержимого транскрипта -> воспроизводимо."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured(
        self, prompt: object, *, schema: type, prompt_version: str, use_fast_model: bool = False
    ) -> LLMInvocationResult[TopicAssessmentLLM]:
        self.calls += 1
        text = str(prompt)
        no_experience = "не работал" in text
        verdict = TopicAssessmentLLM(
            correctness=not no_experience,
            example=not no_experience,
            personal_contribution=not no_experience,
            confidence=AssessmentConfidence.HIGH,
            explicit_no_experience=no_experience,
            technical_error=False,
            evidence_quote="" if no_experience else "проектировал схему",
            reasoning_summary="stub",
        )
        return LLMInvocationResult(
            content=verdict, model_version="stub-model", prompt_version=prompt_version
        )


def _report_by_id(report: dict) -> dict[str, dict]:
    return {c["id"]: c for c in report["candidates"]}


@pytest.mark.anyio
async def test_run_batch_produces_report() -> None:
    candidates = load_input(SAMPLE)
    report = await run_batch(candidates, llm_client=DeterministicLLM(), model_version="stub-model")

    assert report["prompt_version"]
    assert report["model_version"] == "stub-model"
    assert len(report["candidates"]) == 3
    for candidate in report["candidates"]:
        assert "recommendation" in candidate
        assert set(candidate["coverage"]) == {
            "confirmed",
            "needs_check",
            "not_confirmed",
            "mandatory_coverage",
            "desired_coverage",
        }
        assert candidate["topics"]


@pytest.mark.anyio
async def test_statuses_on_examples() -> None:
    candidates = load_input(SAMPLE)
    report = await run_batch(candidates, llm_client=DeterministicLLM())
    by_id = _report_by_id(report)

    # сильный кандидат: оба обязательных подтверждены -> подходит
    strong = by_id["cand-strong"]
    assert all(t["status"] == "confirmed" for t in strong["topics"])
    assert strong["recommendation"] == "fit"

    # пробел: обязательный PostgreSQL «не работал» -> не подтверждён -> не подходит
    gap = by_id["cand-gap"]
    pg = next(t for t in gap["topics"] if t["title"] == "PostgreSQL")
    assert pg["status"] == "not_confirmed"
    assert gap["recommendation"] == "not_fit"

    # пропуск обязательного топика -> не подтверждён -> не подходит
    skip = by_id["cand-skip"]
    assert skip["topics"][0]["status"] == "not_confirmed"
    assert skip["recommendation"] == "not_fit"


@pytest.mark.anyio
async def test_reproducible_same_prompt_version() -> None:
    candidates = load_input(SAMPLE)
    first = await run_batch(candidates, llm_client=DeterministicLLM(), model_version="stub-model")
    second = await run_batch(candidates, llm_client=DeterministicLLM(), model_version="stub-model")
    assert first == second


@pytest.mark.anyio
async def test_skipped_topic_does_not_call_llm() -> None:
    candidates = parse_candidates(
        {
            "candidates": [
                {
                    "id": "c1",
                    "topics": [
                        {
                            "title": "PostgreSQL",
                            "skill_type": "hard",
                            "importance": "mandatory",
                            "question_text": "q",
                            "transcript_segments": [],
                            "skipped": True,
                        }
                    ],
                }
            ]
        }
    )
    fake = DeterministicLLM()
    report = await run_batch(candidates, llm_client=fake)

    assert fake.calls == 0
    assert report["candidates"][0]["topics"][0]["status"] == "not_confirmed"


@pytest.mark.anyio
async def test_load_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "in.csv"
    csv_path.write_text(
        "candidate_id,title,skill_type,importance,question_text,transcript\n"
        "c1,PostgreSQL,hard,mandatory,q,я проектировал схему\n"
        "c1,Kafka,hard,desired,q,настраивал acks\n",
        encoding="utf-8",
    )
    candidates = load_input(csv_path)

    assert len(candidates) == 1
    assert candidates[0].id == "c1"
    assert [t.title for t in candidates[0].topics] == ["PostgreSQL", "Kafka"]
    assert candidates[0].topics[0].transcript_segments[0]["text"] == "я проектировал схему"
