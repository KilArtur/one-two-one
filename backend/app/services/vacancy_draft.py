"""Черновик вакансии из PDF: разбор матрицы требований моделью."""

from __future__ import annotations

from app.integrations.llm import LangChainLLMClient, get_llm_client
from app.prompts import load_prompt
from app.schemas.vacancy import VacancyDraft

VACANCY_DRAFT_PROMPT = "vacancy_draft"
VACANCY_DRAFT_PROMPT_VERSION = "vacancy-draft-v1"
MAX_TOPICS = 9


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
