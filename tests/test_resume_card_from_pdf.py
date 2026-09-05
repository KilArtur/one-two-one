"""Карточка кандидата из PDF-резюме: навыки, опыт и образование по пунктам."""

from collections.abc import AsyncIterator

import httpx
import pytest
from test_vacancy_draft_from_pdf import _pdf

from app.config import Settings
from app.integrations.llm import LLMClientError, LLMInvocationResult, get_llm_client
from app.main import create_app
from app.schemas.candidate import ResumeDraft
from app.services.resume_draft import render_resume_text

RESUME = ResumeDraft(
    full_name="Иван Петров",
    headline="Backend-разработчик",
    skills=["Python", "FastAPI", "Kafka"],
    experience=["Ozon, backend-разработчик, 2021–2024 — сервисы каталога"],
    education=["МФТИ, прикладная математика, 2020"],
)


class FakeLLMClient:
    """Возвращает готовую карточку или падает как недоступный провайдер."""

    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.prompts: list[str] = []

    async def generate_structured(
        self,
        prompt: object,
        *,
        schema: type[ResumeDraft],
        prompt_version: str,
        use_fast_model: bool = False,
    ) -> LLMInvocationResult[ResumeDraft]:
        self.prompts.append(str(prompt))
        if self.fails:
            raise LLMClientError(
                message="boom",
                model_name="fake",
                prompt_version=prompt_version,
                provider_base_url="http://fake",
            )
        return LLMInvocationResult(
            content=RESUME, model_version="fake-model", prompt_version=prompt_version
        )


@pytest.fixture
async def fake() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
async def client(fake: FakeLLMClient) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(Settings(_env_file=None, app_env="testing"))
    app.dependency_overrides[get_llm_client] = lambda: fake
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


def test_resume_text_keeps_sections_as_bullets() -> None:
    text = render_resume_text(RESUME)

    assert "Навыки:\n- Python" in text
    assert "Опыт:\n- Ozon" in text
    assert "Образование:\n- МФТИ" in text


@pytest.mark.anyio
async def test_resume_pdf_becomes_candidate_card(
    client: httpx.AsyncClient, fake: FakeLLMClient
) -> None:
    files = {"file": ("resume.pdf", _pdf("Python FastAPI Kafka"), "application/pdf")}

    response = await client.post("/candidates/resume-draft", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["full_name"] == "Иван Петров"
    assert body["profile"]["skills"] == ["Python", "FastAPI", "Kafka"]
    assert body["profile"]["education"] == ["МФТИ, прикладная математика, 2020"]
    assert "- Ozon" in body["resume_text"]
    assert "Python FastAPI Kafka" in fake.prompts[0]


@pytest.mark.anyio
async def test_resume_scan_without_text_returns_422(client: httpx.AsyncClient) -> None:
    files = {"file": ("scan.pdf", _pdf(""), "application/pdf")}

    response = await client.post("/candidates/resume-draft", files=files)

    assert response.status_code == 422


@pytest.mark.anyio
async def test_resume_model_failure_returns_503(
    client: httpx.AsyncClient, fake: FakeLLMClient
) -> None:
    fake.fails = True
    files = {"file": ("resume.pdf", _pdf("Python"), "application/pdf")}

    response = await client.post("/candidates/resume-draft", files=files)

    assert response.status_code == 503
