"""Черновик вакансии из PDF: извлечение текста и структурированный разбор моделью."""

import zlib
from collections.abc import AsyncIterator

import httpx
import pytest

from app.config import Settings
from app.integrations.llm import LLMClientError, LLMInvocationResult, get_llm_client
from app.main import create_app
from app.schemas.vacancy import TopicDraft, VacancyDraft
from app.services.pdf_text import PdfExtractionError, extract_pdf_text

DRAFT = VacancyDraft(
    title="Backend-разработчик",
    grade="middle+",
    tasks="Разработка сервисов на FastAPI",
    question_examples="Расскажите про инцидент в проде",
    topics=[
        TopicDraft(
            title="Kafka в production",
            skill_type="hard",
            importance="mandatory",
            requirement_description="Опыт эксплуатации под нагрузкой",
            depth_expectations="Партиционирование, ретраи, лаг",
        )
    ],
)


class FakeLLMClient:
    """Возвращает готовый черновик или падает как недоступный провайдер."""

    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.prompts: list[str] = []

    async def generate_structured(
        self,
        prompt: object,
        *,
        schema: type[VacancyDraft],
        prompt_version: str,
        use_fast_model: bool = False,
    ) -> LLMInvocationResult[VacancyDraft]:
        self.prompts.append(str(prompt))
        if self.fails:
            raise LLMClientError(
                message="boom",
                model_name="fake",
                prompt_version=prompt_version,
                provider_base_url="http://fake",
            )
        return LLMInvocationResult(
            content=DRAFT, model_version="fake-model", prompt_version=prompt_version
        )


def _pdf(text: str) -> bytes:
    """Минимальный одностраничный PDF с текстовым слоем."""
    stream = zlib.compress(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode())
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1) + b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


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


def test_extract_text_from_pdf() -> None:
    assert "Kafka" in extract_pdf_text(_pdf("Kafka in production"))


def test_broken_file_is_rejected() -> None:
    with pytest.raises(PdfExtractionError):
        extract_pdf_text(b"not a pdf at all")


@pytest.mark.anyio
async def test_draft_returns_editable_template(
    client: httpx.AsyncClient, fake: FakeLLMClient
) -> None:
    files = {"file": ("vacancy.pdf", _pdf("Kafka in production"), "application/pdf")}

    response = await client.post("/vacancies/draft", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Backend-разработчик"
    assert body["grade"] == "middle+"
    assert [topic["title"] for topic in body["topics"]] == ["Kafka в production"]
    assert "Kafka in production" in fake.prompts[0]


@pytest.mark.anyio
async def test_scan_without_text_layer_returns_422(client: httpx.AsyncClient) -> None:
    files = {"file": ("scan.pdf", _pdf(""), "application/pdf")}

    response = await client.post("/vacancies/draft", files=files)

    assert response.status_code == 422


@pytest.mark.anyio
async def test_model_failure_returns_503(client: httpx.AsyncClient, fake: FakeLLMClient) -> None:
    fake.fails = True
    files = {"file": ("vacancy.pdf", _pdf("Kafka in production"), "application/pdf")}

    response = await client.post("/vacancies/draft", files=files)

    assert response.status_code == 503
