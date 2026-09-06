"""Подтверждение ядра техспециалистом как условие запуска интервью и персонализация."""

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, get_db
from app.integrations.llm import LLMClientError, LLMInvocationResult, get_llm_client
from app.main import create_app
from app.schemas.question import (
    GeneratedCoreQuestion,
    PersonalizedQuestion,
    PersonalizedQuestions,
)
from app.services.auth import AppRole, create_access_token

SETTINGS = Settings(_env_file=None, app_env="testing", jwt_secret_key="review-test-secret")
RESUME = "Пять лет писал сервисы на FastAPI, дежурил по инцидентам Kafka"


def _headers(role: AppRole) -> dict[str, str]:
    token = create_access_token(username="test", role=role, settings=SETTINGS)
    return {"Authorization": f"Bearer {token}"}


class FakeLLMClient:
    """Ядро вопросов и персонализация с управляемым сбоем."""

    def __init__(self) -> None:
        self.personalization_fails = False
        self.personalization_detail = "дежурства по Kafka"
        self.core_calls = 0

    async def generate_structured(
        self,
        prompt: object,
        *,
        schema: type,
        prompt_version: str,
        use_fast_model: bool = False,
    ) -> LLMInvocationResult:
        if schema is PersonalizedQuestions:
            if self.personalization_fails:
                raise LLMClientError(
                    message="boom",
                    model_name="fake",
                    prompt_version=prompt_version,
                    provider_base_url="http://fake",
                )
            content: object = PersonalizedQuestions(
                items=[
                    PersonalizedQuestion(
                        topic="Kafka",
                        resume_detail=self.personalization_detail,
                        question=(
                            "Расскажите про дежурства по Kafka в вашем последнем проекте"
                            if self.personalization_detail
                            else "Базовый вопрос 1"
                        ),
                    )
                ]
            )
        else:
            self.core_calls += 1
            content = GeneratedCoreQuestion(
                text=f"Базовый вопрос {self.core_calls}",
                pattern="experience",
                source_reason="Проверяет требование топика",
            )
        return LLMInvocationResult(
            content=content, model_version="fake-model", prompt_version=prompt_version
        )


@pytest.fixture
async def fake() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
async def client(fake: FakeLLMClient) -> AsyncIterator[httpx.AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    app = create_app(SETTINGS)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = lambda: fake
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    await engine.dispose()


async def _vacancy_with_questions(client: httpx.AsyncClient) -> tuple[str, list[dict]]:
    payload = {
        "title": "Backend",
        "grade": "middle",
        "topics": [{"title": "Kafka", "skill_type": "hard", "importance": "mandatory"}],
    }
    vacancy = (await client.post("/vacancies", json=payload)).json()
    questions = (await client.post(f"/vacancies/{vacancy['id']}/core-questions")).json()
    return vacancy["id"], questions


async def _invite(client: httpx.AsyncClient, vacancy_id: str, resume: str | None = None):
    return await client.post(
        "/candidates",
        headers=_headers(AppRole.RECRUITER),
        json={"vacancy_id": vacancy_id, "resume_text": resume},
    )


@pytest.mark.anyio
async def test_interview_is_blocked_until_questions_are_approved(
    client: httpx.AsyncClient,
) -> None:
    vacancy_id, _ = await _vacancy_with_questions(client)

    blocked = await _invite(client, vacancy_id)

    assert blocked.status_code == 409
    assert "не подтвердил" in blocked.json()["detail"]

    approved = await client.post(
        f"/vacancies/{vacancy_id}/questions/approve", headers=_headers(AppRole.TECH_SPECIALIST)
    )
    assert approved.status_code == 200
    assert all(question["reviewed_by_expert"] for question in approved.json())
    assert (await _invite(client, vacancy_id)).status_code == 201


@pytest.mark.anyio
async def test_specialist_edits_question_and_approval_resets(client: httpx.AsyncClient) -> None:
    vacancy_id, questions = await _vacancy_with_questions(client)
    await client.post(
        f"/vacancies/{vacancy_id}/questions/approve", headers=_headers(AppRole.TECH_SPECIALIST)
    )

    edited = await client.patch(
        f"/vacancies/{vacancy_id}/questions/{questions[0]['id']}",
        headers=_headers(AppRole.TECH_SPECIALIST),
        json={"text": "Как вы разбирали лаг консьюмера?"},
    )

    assert edited.status_code == 200
    assert edited.json()["text"] == "Как вы разбирали лаг консьюмера?"
    assert edited.json()["reviewed_by_expert"] is False
    assert (await _invite(client, vacancy_id)).status_code == 409


@pytest.mark.anyio
async def test_specialist_approves_single_question_without_editing(
    client: httpx.AsyncClient,
) -> None:
    vacancy_id, questions = await _vacancy_with_questions(client)

    approved = await client.post(
        f"/vacancies/{vacancy_id}/questions/{questions[0]['id']}/approve",
        headers=_headers(AppRole.TECH_SPECIALIST),
    )

    assert approved.status_code == 200
    assert approved.json()["reviewed_by_expert"] is True
    assert approved.json()["text"] == questions[0]["text"]


@pytest.mark.anyio
async def test_specialist_can_unapprove_questions(client: httpx.AsyncClient) -> None:
    vacancy_id, questions = await _vacancy_with_questions(client)
    await client.post(
        f"/vacancies/{vacancy_id}/questions/approve", headers=_headers(AppRole.TECH_SPECIALIST)
    )

    one = await client.post(
        f"/vacancies/{vacancy_id}/questions/{questions[0]['id']}/unapprove",
        headers=_headers(AppRole.TECH_SPECIALIST),
    )
    assert one.status_code == 200
    assert one.json()["reviewed_by_expert"] is False

    await client.post(
        f"/vacancies/{vacancy_id}/questions/approve", headers=_headers(AppRole.TECH_SPECIALIST)
    )
    all_rows = await client.post(
        f"/vacancies/{vacancy_id}/questions/unapprove", headers=_headers(AppRole.TECH_SPECIALIST)
    )
    assert all_rows.status_code == 200
    assert all(not question["reviewed_by_expert"] for question in all_rows.json())
    assert (await _invite(client, vacancy_id)).status_code == 409


@pytest.mark.anyio
async def test_only_technical_specialist_reviews_questions(client: httpx.AsyncClient) -> None:
    vacancy_id, questions = await _vacancy_with_questions(client)

    approve = await client.post(
        f"/vacancies/{vacancy_id}/questions/approve", headers=_headers(AppRole.RECRUITER)
    )
    approve_one = await client.post(
        f"/vacancies/{vacancy_id}/questions/{questions[0]['id']}/approve",
        headers=_headers(AppRole.RECRUITER),
    )
    edit = await client.patch(
        f"/vacancies/{vacancy_id}/questions/{questions[0]['id']}",
        headers=_headers(AppRole.RECRUITER),
        json={"text": "Свой вопрос"},
    )

    assert approve.status_code == 403
    assert approve_one.status_code == 403
    assert edit.status_code == 403


@pytest.mark.anyio
async def test_approval_requires_questions_for_every_topic(client: httpx.AsyncClient) -> None:
    payload = {
        "title": "Backend",
        "grade": "middle",
        "topics": [{"title": "Kafka", "skill_type": "hard", "importance": "mandatory"}],
    }
    vacancy = (await client.post("/vacancies", json=payload)).json()

    response = await client.post(
        f"/vacancies/{vacancy['id']}/questions/approve", headers=_headers(AppRole.TECH_SPECIALIST)
    )

    assert response.status_code == 409


@pytest.mark.anyio
async def test_personal_question_replaces_core_for_candidate(client: httpx.AsyncClient) -> None:
    vacancy_id, questions = await _vacancy_with_questions(client)
    await client.post(
        f"/vacancies/{vacancy_id}/questions/approve", headers=_headers(AppRole.TECH_SPECIALIST)
    )

    candidate = (await _invite(client, vacancy_id, RESUME)).json()
    link = (
        await client.post(
            f"/candidates/{candidate['id']}/interview-link", headers=_headers(AppRole.RECRUITER)
        )
    ).json()
    exchanged = await client.post("/candidate-auth/exchange", json={"token": link["token"]})
    candidate_headers = {"Authorization": f"Bearer {exchanged.json()['access_token']}"}
    await client.post("/candidate-auth/consent", json={"accepted": True}, headers=candidate_headers)

    visible = (await client.get("/candidate-interview/questions", headers=candidate_headers)).json()

    assert len(visible) == 1
    assert visible[0]["type"] == "personal"
    assert visible[0]["text"] == "Расскажите про дежурства по Kafka в вашем последнем проекте"
    assert visible[0]["id"] != questions[0]["id"]


@pytest.mark.anyio
async def test_candidate_without_resume_keeps_core_questions(client: httpx.AsyncClient) -> None:
    vacancy_id, questions = await _vacancy_with_questions(client)
    await client.post(
        f"/vacancies/{vacancy_id}/questions/approve", headers=_headers(AppRole.TECH_SPECIALIST)
    )

    candidate = (await _invite(client, vacancy_id)).json()
    link = (
        await client.post(
            f"/candidates/{candidate['id']}/interview-link", headers=_headers(AppRole.RECRUITER)
        )
    ).json()
    exchanged = await client.post("/candidate-auth/exchange", json={"token": link["token"]})
    candidate_headers = {"Authorization": f"Bearer {exchanged.json()['access_token']}"}
    await client.post("/candidate-auth/consent", json={"accepted": True}, headers=candidate_headers)

    visible = (await client.get("/candidate-interview/questions", headers=candidate_headers)).json()

    assert [item["id"] for item in visible] == [questions[0]["id"]]


@pytest.mark.anyio
async def test_resume_without_relevant_detail_keeps_core(
    client: httpx.AsyncClient, fake: FakeLLMClient
) -> None:
    # Резюме есть, но по теме топика ничего нет: resume_detail пуст -> остаётся каркас.
    vacancy_id, questions = await _vacancy_with_questions(client)
    await client.post(
        f"/vacancies/{vacancy_id}/questions/approve", headers=_headers(AppRole.TECH_SPECIALIST)
    )
    fake.personalization_detail = ""

    candidate = (await _invite(client, vacancy_id, RESUME)).json()
    link = (
        await client.post(
            f"/candidates/{candidate['id']}/interview-link", headers=_headers(AppRole.RECRUITER)
        )
    ).json()
    exchanged = await client.post("/candidate-auth/exchange", json={"token": link["token"]})
    candidate_headers = {"Authorization": f"Bearer {exchanged.json()['access_token']}"}
    await client.post("/candidate-auth/consent", json={"accepted": True}, headers=candidate_headers)

    visible = (await client.get("/candidate-interview/questions", headers=candidate_headers)).json()
    assert [item["id"] for item in visible] == [questions[0]["id"]]
    assert visible[0]["type"] == "core"


@pytest.mark.anyio
async def test_personalization_failure_does_not_block_invite(
    client: httpx.AsyncClient, fake: FakeLLMClient
) -> None:
    vacancy_id, questions = await _vacancy_with_questions(client)
    await client.post(
        f"/vacancies/{vacancy_id}/questions/approve", headers=_headers(AppRole.TECH_SPECIALIST)
    )
    fake.personalization_fails = True

    created = await _invite(client, vacancy_id, RESUME)

    assert created.status_code == 201
    listed = (await client.get(f"/vacancies/{vacancy_id}/questions")).json()
    assert [item["id"] for item in listed] == [questions[0]["id"]]


@pytest.mark.anyio
async def test_recruiter_deletes_candidate(client: httpx.AsyncClient) -> None:
    vacancy_id, _ = await _vacancy_with_questions(client)
    await client.post(
        f"/vacancies/{vacancy_id}/questions/approve", headers=_headers(AppRole.TECH_SPECIALIST)
    )
    created = await _invite(client, vacancy_id, RESUME)
    candidate_id = created.json()["id"]

    forbidden = await client.delete(
        f"/candidates/{candidate_id}", headers=_headers(AppRole.TECH_SPECIALIST)
    )
    assert forbidden.status_code == 403

    deleted = await client.delete(
        f"/candidates/{candidate_id}", headers=_headers(AppRole.RECRUITER)
    )
    assert deleted.status_code == 204
    assert (
        await client.get(f"/candidates/{candidate_id}/result", headers=_headers(AppRole.RECRUITER))
    ).status_code == 404
