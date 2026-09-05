"""Черновик вакансии из PDF: извлечение текста и разбор матрицы требований моделью."""

from __future__ import annotations

import io

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.integrations.llm import LangChainLLMClient, get_llm_client
from app.prompts import load_prompt
from app.schemas.vacancy import VacancyDraft

VACANCY_DRAFT_PROMPT = "vacancy_draft"
VACANCY_DRAFT_PROMPT_VERSION = "vacancy-draft-v1"
MAX_DOCUMENT_CHARS = 40000
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_TOPICS = 9


class PdfExtractionError(Exception):
    """Файл не читается как PDF или не содержит текстового слоя."""


def extract_pdf_text(data: bytes) -> str:
    """Извлекает текстовый слой PDF; сканы без текста считаются нечитаемыми."""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PyPdfError, ValueError) as exc:
        raise PdfExtractionError("Не удалось прочитать PDF") from exc
    text = "\n".join(pages).strip()
    if not text:
        raise PdfExtractionError("В PDF нет текстового слоя — нужен файл с текстом, не скан")
    return text[:MAX_DOCUMENT_CHARS]


async def build_vacancy_draft(
    document_text: str, *, llm_client: LangChainLLMClient | None = None
) -> VacancyDraft:
    """Разбирает текст документа в черновик вакансии с топиками."""
    llm_client = llm_client or get_llm_client()
    prompt = load_prompt(VACANCY_DRAFT_PROMPT).format(document_text=document_text)
    result = await llm_client.generate_structured(
        prompt,
        schema=VacancyDraft,
        prompt_version=VACANCY_DRAFT_PROMPT_VERSION,
    )
    draft: VacancyDraft = result.content
    return draft.model_copy(update={"topics": draft.topics[:MAX_TOPICS]})
