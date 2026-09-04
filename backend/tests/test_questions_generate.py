"""Core question generation tests (TASK-014 / M2)."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.questions import get_llm_client
from app.config import get_settings
from app.integrations.llm import LLMError, LLMResult
from app.main import create_app
from app.models.enums import QuestionPattern
from app.prompts import load_prompt
from app.services.questions import _CoreQuestionDraft, _CoreQuestionsLLMOutput


def _topic(title: str, order: int = 0) -> dict[str, object]:
    return {
        "title": title,
        "skill_type": "hard",
        "importance": "mandatory",
        "requirement_description": f"Need {title}",
        "depth_expectations": "Hands-on",
        "verifiable_by_interview": True,
        "order": order,
    }


def _topics(n: int, prefix: str = "Topic") -> list[dict[str, object]]:
    return [_topic(f"{prefix}-{i}", i) for i in range(1, n + 1)]


def _fake_llm_output(topic_ids: list[str]) -> _CoreQuestionsLLMOutput:
    patterns = list(QuestionPattern)
    questions = [
        _CoreQuestionDraft(
            topic_id=uuid.UUID(topic_id),
            pattern=patterns[i % len(patterns)],
            text=f"Core question for topic {i + 1}?",
            source_reason=f"Checks requirement of topic {i + 1}",
        )
        for i, topic_id in enumerate(topic_ids)
    ]
    return _CoreQuestionsLLMOutput(questions=questions)


class _FakeLLM:
    """LLMClient stand-in that records calls and returns canned structured output."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def acomplete_structured(
        self,
        prompt: str,
        schema: type[_CoreQuestionsLLMOutput],
        *,
        prompt_version: str,
        role: Any = None,
        system: str | None = None,
    ) -> LLMResult[_CoreQuestionsLLMOutput]:
        self.calls += 1
        if self.fail:
            raise LLMError("simulated network failure")

        # Extract topic_ids from the JSON blob in the user prompt.
        match = re.search(r"\{[\s\S]*\}\s*$", prompt)
        assert match is not None
        payload = json.loads(match.group(0))
        topic_ids = [t["topic_id"] for t in payload["topics"]]
        content = _fake_llm_output(topic_ids)
        assert schema is _CoreQuestionsLLMOutput
        assert system
        assert prompt_version
        return LLMResult(
            content=content,
            model_version="test-model",
            prompt_version=prompt_version,
        )


def _app_with_llm(fake: _FakeLLM) -> Any:
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_llm_client] = lambda: fake
    return application


@pytest.mark.asyncio
async def test_generate_core_questions_creates_one_per_topic() -> None:
    """Шаг 1: POST generate — в БД появляются N вопросов type=core."""
    fake = _FakeLLM()
    app = _app_with_llm(fake)
    n = 5
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        created = await client.post(
            "/vacancies",
            json={
                "title": f"Gen-{uuid.uuid4().hex[:8]}",
                "grade": "middle",
                "status": "draft",
                "topics": _topics(n, "Core"),
            },
        )
        assert created.status_code == 201
        vacancy = created.json()
        vacancy_id = vacancy["id"]
        assert len(vacancy["topics"]) == n

        response = await client.post(f"/vacancies/{vacancy_id}/questions/generate")
        assert response.status_code == 200
        body = response.json()
        assert body["vacancy_id"] == vacancy_id
        assert body["cached"] is False
        assert body["prompt_version"] == "core-questions-v1"
        assert body["model_version"] == "test-model"
        assert len(body["questions"]) == n
        assert all(q["type"] == "core" for q in body["questions"])
        assert all(q["source_reason"] for q in body["questions"])
        assert fake.calls == 1

        listed = await client.get(f"/vacancies/{vacancy_id}/questions")
        assert listed.status_code == 200
        assert len(listed.json()) == n


@pytest.mark.asyncio
async def test_generate_core_questions_patterns_valid() -> None:
    """Шаг 2: каждый имеет pattern из {technical, experience, reasoning}."""
    fake = _FakeLLM()
    app = _app_with_llm(fake)
    allowed = {p.value for p in QuestionPattern}
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        created = await client.post(
            "/vacancies",
            json={
                "title": f"Pat-{uuid.uuid4().hex[:8]}",
                "grade": "senior",
                "topics": _topics(6, "Pat"),
            },
        )
        vacancy_id = created.json()["id"]
        response = await client.post(f"/vacancies/{vacancy_id}/questions/generate")
        assert response.status_code == 200
        patterns = {q["pattern"] for q in response.json()["questions"]}
        assert patterns <= allowed
        assert patterns  # at least one


@pytest.mark.asyncio
async def test_generate_core_questions_cached_no_duplicate() -> None:
    """Шаг 3: повторный вызов не дублирует вопросы и не зовёт LLM."""
    fake = _FakeLLM()
    app = _app_with_llm(fake)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        created = await client.post(
            "/vacancies",
            json={
                "title": f"Cache-{uuid.uuid4().hex[:8]}",
                "grade": "junior",
                "topics": _topics(5, "Cache"),
            },
        )
        vacancy_id = created.json()["id"]

        first = await client.post(f"/vacancies/{vacancy_id}/questions/generate")
        assert first.status_code == 200
        first_ids = sorted(q["id"] for q in first.json()["questions"])
        assert fake.calls == 1

        second = await client.post(f"/vacancies/{vacancy_id}/questions/generate")
        assert second.status_code == 200
        second_body = second.json()
        assert second_body["cached"] is True
        second_ids = sorted(q["id"] for q in second_body["questions"])
        assert second_ids == first_ids
        assert fake.calls == 1  # no second LLM call

        listed = await client.get(f"/vacancies/{vacancy_id}/questions")
        assert len(listed.json()) == 5


@pytest.mark.asyncio
async def test_llm_failure_does_not_block_vacancy() -> None:
    """Acceptance: сбой генерации не блокирует вакансию (нет частичных записей)."""
    fake = _FakeLLM(fail=True)
    app = _app_with_llm(fake)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        created = await client.post(
            "/vacancies",
            json={
                "title": f"Fail-{uuid.uuid4().hex[:8]}",
                "grade": "middle",
                "topics": _topics(5, "Fail"),
            },
        )
        vacancy_id = created.json()["id"]

        response = await client.post(f"/vacancies/{vacancy_id}/questions/generate")
        assert response.status_code == 502

        vacancy = await client.get(f"/vacancies/{vacancy_id}")
        assert vacancy.status_code == 200
        assert vacancy.json()["id"] == vacancy_id

        listed = await client.get(f"/vacancies/{vacancy_id}/questions")
        assert listed.status_code == 200
        assert listed.json() == []


def test_load_core_questions_prompt() -> None:
    prompt = load_prompt("generate_core_questions")
    assert prompt.version == "core-questions-v1"
    assert "pattern" in prompt.body.lower() or "technical" in prompt.body.lower()


@pytest.mark.asyncio
async def test_generate_404_for_unknown_vacancy() -> None:
    fake = _FakeLLM()
    app = _app_with_llm(fake)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/vacancies/{uuid.uuid4()}/questions/generate",
        )
        assert response.status_code == 404
