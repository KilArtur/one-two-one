"""Карточка кандидата из PDF-резюме: структурированный разбор моделью."""

from __future__ import annotations

from app.integrations.llm import LangChainLLMClient, get_llm_client
from app.prompts import load_prompt
from app.schemas.candidate import ResumeCard, ResumeDraft

RESUME_DRAFT_PROMPT = "resume_draft"
RESUME_DRAFT_PROMPT_VERSION = "resume-draft-v2"
MAX_SKILLS = 30
MAX_EXPERIENCE = 12
MAX_EDUCATION = 5


def render_resume_text(draft: ResumeDraft) -> str:
    """Собирает извлечённое основное в текст, по которому персонализируются вопросы."""
    blocks: list[str] = []
    if draft.full_name:
        blocks.append(draft.full_name)
    if draft.headline:
        blocks.append(draft.headline)
    for title, items in (
        ("Навыки", draft.skills),
        ("Опыт", draft.experience),
        ("Образование", draft.education),
    ):
        if items:
            blocks.append("\n".join([f"{title}:", *(f"- {item}" for item in items)]))
    return "\n\n".join(blocks)


async def build_resume_card(
    document_text: str, *, llm_client: LangChainLLMClient | None = None
) -> ResumeCard:
    """Из уже извлечённого текста PDF забирает моделью основное — как черновик вакансии."""
    source = document_text.strip()
    llm_client = llm_client or get_llm_client()
    prompt = load_prompt(RESUME_DRAFT_PROMPT).format(document_text=source)
    result = await llm_client.generate_structured(
        prompt,
        schema=ResumeDraft,
        prompt_version=RESUME_DRAFT_PROMPT_VERSION,
    )
    draft: ResumeDraft = result.content.model_copy(
        update={
            "skills": result.content.skills[:MAX_SKILLS],
            "experience": result.content.experience[:MAX_EXPERIENCE],
            "education": result.content.education[:MAX_EDUCATION],
        }
    )
    return ResumeCard(
        profile=draft,
        resume_text=render_resume_text(draft),
        source_text=source,
        parsed_by_model=True,
    )


def fallback_resume_card(document_text: str) -> ResumeCard:
    """Если модель недоступна, оставляем только текст из PDF."""
    source = document_text.strip()
    return ResumeCard(
        profile=ResumeDraft(full_name="", headline="", skills=[], experience=[], education=[]),
        resume_text=source,
        source_text=source,
        parsed_by_model=False,
    )
