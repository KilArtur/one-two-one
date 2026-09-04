"""Core question generation endpoints (TASK-014 / M2)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.integrations.llm import LLMClient
from app.schemas.question import GenerateCoreQuestionsResponse, QuestionRead
from app.services import questions as questions_service
from app.services.questions import QuestionGenerationError

router = APIRouter(
    prefix="/vacancies/{vacancy_id}/questions",
    tags=["questions"],
)


def get_llm_client() -> LLMClient:
    """FastAPI dependency for the LangChain LLM client."""
    return LLMClient()


@router.post(
    "/generate",
    response_model=GenerateCoreQuestionsResponse,
    status_code=status.HTTP_200_OK,
)
async def generate_core_questions(
    vacancy_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[LLMClient, Depends(get_llm_client)],
) -> GenerateCoreQuestionsResponse:
    """Generate core questions (one per topic) or return the DB cache."""
    try:
        result = await questions_service.generate_core_questions(
            session,
            vacancy_id,
            llm=llm,
        )
    except QuestionGenerationError as exc:
        # Vacancy left unchanged; generation failure must not block the vacancy.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    return GenerateCoreQuestionsResponse(
        vacancy_id=result.vacancy_id,
        cached=result.cached,
        model_version=result.model_version,
        prompt_version=result.prompt_version,
        questions=[QuestionRead.model_validate(q) for q in result.questions],
    )


@router.get("", response_model=list[QuestionRead])
async def list_core_questions(
    vacancy_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[QuestionRead]:
    questions = await questions_service.list_core_questions(session, vacancy_id)
    if questions is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return [QuestionRead.model_validate(q) for q in questions]
