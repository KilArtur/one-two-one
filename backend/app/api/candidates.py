"""API досрочного удаления данных кандидата по запросу (Р18)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.integrations.llm import LangChainLLMClient, LLMClientError, get_llm_client
from app.integrations.storage import S3StorageClient, get_s3_storage_client
from app.models.candidate import Candidate
from app.models.vacancy import Vacancy
from app.schemas.candidate import ResumeCard
from app.services.auth import CurrentUser, ensure_interview_link_issue_allowed, get_current_user
from app.services.candidate_overview import list_vacancy_candidates
from app.services.pdf_text import MAX_DOCUMENT_BYTES, PdfExtractionError, extract_pdf_text
from app.services.question_personalization import personalize_questions
from app.services.question_review import QUESTIONS_NOT_APPROVED, questions_approved
from app.services.result_card import build_result_card
from app.services.result_links import get_result_user
from app.services.resume_draft import build_resume_card
from app.services.retention import purge_candidate

router = APIRouter(prefix="/candidates", tags=["candidates"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
StorageDep = Annotated[S3StorageClient, Depends(get_s3_storage_client)]
LLMDep = Annotated[LangChainLLMClient, Depends(get_llm_client)]


class CandidateCreate(BaseModel):
    """Create an invitation for a vacancy without requiring a resume."""

    vacancy_id: uuid.UUID
    resume_text: str | None = Field(default=None, max_length=50000)


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    vacancy_id: uuid.UUID
    status: str


@router.post("", response_model=CandidateRead, status_code=201)
async def create_candidate(
    data: CandidateCreate, current_user: CurrentUserDep, session: SessionDep, llm: LLMDep
) -> Candidate:
    """Allow a recruiter to create a candidate from the staff interface."""
    ensure_interview_link_issue_allowed(current_user)
    vacancy = await session.get(Vacancy, data.vacancy_id)
    if vacancy is None:
        raise HTTPException(404, "Vacancy not found")
    if not await questions_approved(session, vacancy.id):
        raise HTTPException(409, QUESTIONS_NOT_APPROVED)
    candidate = Candidate(vacancy_id=data.vacancy_id, resume_text=data.resume_text)
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)
    await personalize_questions(session, candidate.id, llm_client=llm)
    return candidate


@router.post("/resume-draft", response_model=ResumeCard)
async def draft_resume_card(file: UploadFile, llm: LLMDep) -> ResumeCard:
    """Разбирает PDF-резюме в карточку кандидата; ничего не сохраняет."""
    try:
        data = await file.read(MAX_DOCUMENT_BYTES + 1)
    finally:
        await file.close()
    if len(data) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Файл больше 10 МБ")
    try:
        text = extract_pdf_text(data)
    except PdfExtractionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    try:
        return await build_resume_card(text, llm_client=llm)
    except LLMClientError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Модель недоступна, вставьте резюме текстом"
        ) from exc


class PurgeRequest(BaseModel):
    reason: str = Field(default="on_request", min_length=1, max_length=500)


class PurgeResult(BaseModel):
    candidate_id: uuid.UUID
    reason: str
    details: dict | None


@router.post("/{candidate_id}/purge", response_model=PurgeResult)
async def purge_candidate_data(
    candidate_id: uuid.UUID,
    data: PurgeRequest,
    current_user: CurrentUserDep,
    session: SessionDep,
    storage: StorageDep,
) -> PurgeResult:
    """Досрочно удаляет ПДн кандидата и логирует факт удаления."""
    log = await purge_candidate(session, storage, candidate_id, reason=data.reason, force_log=True)
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return PurgeResult(candidate_id=candidate_id, reason=log.reason, details=log.details)


class CandidateOverviewRead(BaseModel):
    """Кандидат в списке рекрутера: статус обработки и тройка чисел (без AI-score)."""

    model_config = ConfigDict(from_attributes=True)

    candidate_id: uuid.UUID
    candidate_status: str
    processing_status: str
    confirmed_count: int
    needs_check_count: int
    not_confirmed_count: int
    recommendation: str | None


@router.get("", response_model=list[CandidateOverviewRead])
async def list_candidates(
    vacancy_id: uuid.UUID,
    current_user: CurrentUserDep,
    session: SessionDep,
    processing_status: str | None = None,
) -> list[CandidateOverviewRead]:
    """Список кандидатов вакансии со статусами обработки и тройкой чисел."""
    overviews = await list_vacancy_candidates(
        session, vacancy_id, processing_status=processing_status
    )
    return [CandidateOverviewRead.model_validate(item) for item in overviews]


class ResultTopicRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    topic_id: uuid.UUID
    topic_title: str
    skill_type: str
    importance: str
    system_status: str
    current_status: str
    author: str
    reasoning_summary: str | None
    has_evidence: bool = False


class ResultCardRead(BaseModel):
    """Карточка результата: матрица топиков первым блоком, рекомендация, слои резюме/интервью."""

    model_config = ConfigDict(from_attributes=True)

    candidate_id: uuid.UUID
    recommendation: str
    recommendation_reason: str
    confirmed_count: int
    needs_check_count: int
    not_confirmed_count: int
    mandatory_coverage: float | None
    desired_coverage: float | None
    resume_text: str | None
    topics: list[ResultTopicRowRead]


@router.get("/{candidate_id}/result", response_model=ResultCardRead)
async def read_result_card(
    candidate_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_result_user)],
    session: SessionDep,
) -> ResultCardRead:
    """Карточка результата кандидата (матрица топиков, рекомендация Р5, coverage)."""
    card = await build_result_card(session, candidate_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return ResultCardRead.model_validate(card)
