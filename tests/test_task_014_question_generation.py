"""Генерация ядра вопросов через LLM с кешем и устойчивостью к сбою (TASK-014)."""

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, get_db
from app.integrations.llm import LLMClientError, LLMInvocationResult, get_llm_client
from app.main import create_app
from app.models.question import QuestionPattern
from app.schemas.question import GeneratedCoreQuestion

_PATTERNS = [QuestionPattern.TECHNICAL, QuestionPattern.EXPERIENCE, QuestionPattern.REASONING]


class FakeLLMClient:
    """LLM-клиент-заглушка: детерминированный ответ, опциональный сбой по подстроке."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls = 0
        self.fail_on = fail_on

    async def generate_structured(
        self,
        prompt: object,
        *,
        schema: type[GeneratedCoreQuestion],
        prompt_version: str,
        use_fast_model: bool = False,
    ) -> LLMInvocationResult[GeneratedCoreQuestion]:
        if self.fail_on is not None and self.fail_on in str(prompt):
            raise LLMClientError(
                message="boom",
                model_name="fake",
                prompt_version=prompt_version,
                provider_base_url="http://fake",
            )
        index = self.calls
        self.calls += 1
        return LLMInvocationResult(
            content=GeneratedCoreQuestion(
                text=f"Вопрос {index}",
                pattern=_PATTERNS[index % len(_PATTERNS)],
                source_reason=f"Проверяет требование {index}",
            ),
            model_version="fake-model",
            prompt_version=prompt_version,
        )


def _make_client(fake: FakeLLMClient) -> tuple[httpx.AsyncClient, object]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    app = create_app(Settings(_env_file=None, app_env="testing"))
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = lambda: fake
    return app, engine


@pytest.fixture
async def fake() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
async def client(fake: FakeLLMClient) -> AsyncIterator[httpx.AsyncClient]:
    app, engine = _make_client(fake)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
    await engine.dispose()


def _topic(title: str, order: int) -> dict:
    return {"title": title, "skill_type": "hard", "importance": "mandatory", "order": order}


async def _create_vacancy(client: httpx.AsyncClient, n_topics: int) -> dict:
    payload = {
        "title": "Backend",
        "grade": "middle",
        "topics": [_topic(f"Топик {i}", i) for i in range(n_topics)],
    }
    return (await client.post("/vacancies", json=payload)).json()


@pytest.mark.anyio
async def test_generate_one_core_question_per_topic(client: httpx.AsyncClient) -> None:
    vacancy = await _create_vacancy(client, 3)

    resp = await client.post(f"/vacancies/{vacancy['id']}/core-questions")

    assert resp.status_code == 200
    questions = resp.json()
    assert len(questions) == 3
    assert all(q["type"] == "core" for q in questions)
    assert all(q["source_reason"] for q in questions)


@pytest.mark.anyio
async def test_each_question_has_allowed_pattern(client: httpx.AsyncClient) -> None:
    vacancy = await _create_vacancy(client, 3)

    questions = (await client.post(f"/vacancies/{vacancy['id']}/core-questions")).json()

    allowed = {"technical", "experience", "reasoning"}
    assert all(q["pattern"] in allowed for q in questions)


@pytest.mark.anyio
async def test_repeat_call_does_not_duplicate(
    client: httpx.AsyncClient, fake: FakeLLMClient
) -> None:
    vacancy = await _create_vacancy(client, 3)

    first = (await client.post(f"/vacancies/{vacancy['id']}/core-questions")).json()
    assert fake.calls == 3

    second = (await client.post(f"/vacancies/{vacancy['id']}/core-questions")).json()

    # повторный вызов не обращается к LLM и не создаёт дублей
    assert fake.calls == 3
    assert len(second) == 3
    assert {q["id"] for q in first} == {q["id"] for q in second}


@pytest.mark.anyio
async def test_llm_failure_does_not_block_other_topics() -> None:
    fake = FakeLLMClient(fail_on="Топик 1")
    app, engine = _make_client(fake)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        vacancy = await _create_vacancy(client, 3)
        resp = await client.post(f"/vacancies/{vacancy['id']}/core-questions")
    await engine.dispose()

    assert resp.status_code == 200
    # один топик упал на генерации, остальные два сгенерированы — вакансия не заблокирована
    assert len(resp.json()) == 2
