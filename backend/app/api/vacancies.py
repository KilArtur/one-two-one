"""CRUD-эндпоинты вакансии и топиков с версионированием матрицы (M1) и ASR-словарём."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.integrations.llm import LangChainLLMClient, LLMClientError, get_llm_client
from app.schemas.question import QuestionRead, QuestionTextUpdate
from app.schemas.vacancy import (
    AsrDictionaryRead,
    AsrDictionaryUpdate,
    TopicRead,
    TopicsReplace,
    TopicUpdate,
    TopicWrite,
    VacancyCreate,
    VacancyDraft,
    VacancyRead,
    VacancyUpdate,
)
from app.services import question_generation, question_review
from app.services import vacancy as vacancy_service
from app.services.auth import CurrentUser, ensure_question_review_allowed, get_current_user
from app.services.pdf_text import MAX_DOCUMENT_BYTES, PdfExtractionError, extract_pdf_text
from app.services.question_review import QuestionsIncompleteError
from app.services.vacancy import TopicCountError, VacancyNotDraftError
from app.services.vacancy_draft import build_vacancy_draft

router = APIRouter(prefix="/vacancies", tags=["vacancies"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]
LLMDep = Annotated[LangChainLLMClient, Depends(get_llm_client)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")
_TOPIC_COUNT = HTTPException(
    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    detail=f"Нужен минимум {vacancy_service.MIN_TOPICS} топик",
)
_NOT_DRAFT = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="Индивидуальная правка топиков доступна только черновику; "
    "для активной вакансии используйте замену состава (создаётся новая версия)",
)


@router.post("", response_model=VacancyRead, status_code=status.HTTP_201_CREATED)
async def create_vacancy(data: VacancyCreate, session: SessionDep) -> VacancyRead:
    """Создаёт вакансию версии 1."""
    vacancy = await vacancy_service.create_vacancy(session, data)
    return VacancyRead.model_validate(vacancy)


@router.post("/draft", response_model=VacancyDraft)
async def draft_from_document(file: UploadFile, llm: LLMDep) -> VacancyDraft:
    """Разбирает PDF-описание вакансии в черновик формы; ничего не сохраняет."""
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
        return await build_vacancy_draft(text, llm_client=llm)
    except LLMClientError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Модель недоступна, заполните форму вручную"
        ) from exc


@router.get("", response_model=list[VacancyRead])
async def list_vacancies(session: SessionDep) -> list[VacancyRead]:
    """Список последних версий логических вакансий."""
    vacancies = await vacancy_service.list_vacancies(session)
    return [VacancyRead.model_validate(item) for item in vacancies]


@router.get("/{vacancy_id}", response_model=VacancyRead)
async def get_vacancy(vacancy_id: uuid.UUID, session: SessionDep) -> VacancyRead:
    """Возвращает конкретный снимок вакансии по id."""
    vacancy = await vacancy_service.get_vacancy(session, vacancy_id)
    if vacancy is None:
        raise _NOT_FOUND
    return VacancyRead.model_validate(vacancy)


@router.patch("/{vacancy_id}", response_model=VacancyRead)
async def update_vacancy(
    vacancy_id: uuid.UUID, data: VacancyUpdate, session: SessionDep
) -> VacancyRead:
    """Обновляет скалярные поля вакансии на месте."""
    vacancy = await vacancy_service.update_vacancy(session, vacancy_id, data)
    if vacancy is None:
        raise _NOT_FOUND
    return VacancyRead.model_validate(vacancy)


@router.delete("/{vacancy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vacancy(vacancy_id: uuid.UUID, session: SessionDep) -> None:
    """Удаляет вакансию и все её версии вместе с кандидатами."""
    deleted = await vacancy_service.delete_vacancy(session, vacancy_id)
    if not deleted:
        raise _NOT_FOUND


@router.put("/{vacancy_id}/topics", response_model=VacancyRead)
async def replace_topics(
    vacancy_id: uuid.UUID, data: TopicsReplace, session: SessionDep
) -> VacancyRead:
    """Сохраняет состав топиков (5–9); для активной вакансии создаёт новую версию-снимок."""
    try:
        vacancy = await vacancy_service.replace_topics(session, vacancy_id, data.topics)
    except TopicCountError as exc:
        raise _TOPIC_COUNT from exc
    if vacancy is None:
        raise _NOT_FOUND
    return VacancyRead.model_validate(vacancy)


@router.post(
    "/{vacancy_id}/topics",
    response_model=TopicRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_topic(vacancy_id: uuid.UUID, data: TopicWrite, session: SessionDep) -> TopicRead:
    """Добавляет один топик в черновик вакансии."""
    try:
        topic = await vacancy_service.add_topic(session, vacancy_id, data)
    except VacancyNotDraftError as exc:
        raise _NOT_DRAFT from exc
    except TopicCountError as exc:
        raise _TOPIC_COUNT from exc
    if topic is None:
        raise _NOT_FOUND
    return TopicRead.model_validate(topic)


@router.patch("/{vacancy_id}/topics/{topic_id}", response_model=TopicRead)
async def update_topic(
    vacancy_id: uuid.UUID,
    topic_id: uuid.UUID,
    data: TopicUpdate,
    session: SessionDep,
) -> TopicRead:
    """Редактирует топик черновика."""
    try:
        topic = await vacancy_service.update_topic(session, vacancy_id, topic_id, data)
    except VacancyNotDraftError as exc:
        raise _NOT_DRAFT from exc
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return TopicRead.model_validate(topic)


@router.delete("/{vacancy_id}/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(vacancy_id: uuid.UUID, topic_id: uuid.UUID, session: SessionDep) -> None:
    """Удаляет топик из черновика вакансии."""
    try:
        result = await vacancy_service.delete_topic(session, vacancy_id, topic_id)
    except VacancyNotDraftError as exc:
        raise _NOT_DRAFT from exc
    if result is None:
        raise _NOT_FOUND
    if result is False:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")


@router.post("/{vacancy_id}/core-questions", response_model=list[QuestionRead])
async def generate_core_questions(
    vacancy_id: uuid.UUID, session: SessionDep, llm: LLMDep
) -> list[QuestionRead]:
    """Генерирует ядро вопросов вакансии (1 core-вопрос на топик); повторный вызов не дублирует."""
    questions = await question_generation.generate_core_questions(
        session, vacancy_id, llm_client=llm
    )
    if questions is None:
        raise _NOT_FOUND
    return [QuestionRead.model_validate(question) for question in questions]


@router.get("/{vacancy_id}/questions", response_model=list[QuestionRead])
async def read_core_questions(vacancy_id: uuid.UUID, session: SessionDep) -> list[QuestionRead]:
    """Отдаёт ядро вопросов вакансии для ревью техспециалистом."""
    questions = await question_review.list_core_questions(session, vacancy_id)
    return [QuestionRead.model_validate(question) for question in questions]


@router.patch("/{vacancy_id}/questions/{question_id}", response_model=QuestionRead)
async def edit_core_question(
    vacancy_id: uuid.UUID,
    question_id: uuid.UUID,
    data: QuestionTextUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> QuestionRead:
    """Меняет формулировку core-вопроса; подтверждение ядра при этом сбрасывается."""
    ensure_question_review_allowed(current_user)
    question = await question_review.update_question_text(
        session, vacancy_id, question_id, data.text
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return QuestionRead.model_validate(question)


@router.post("/{vacancy_id}/questions/{question_id}/approve", response_model=QuestionRead)
async def approve_core_question(
    vacancy_id: uuid.UUID,
    question_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> QuestionRead:
    """Подтверждает один core-вопрос как есть, без правки формулировки."""
    ensure_question_review_allowed(current_user)
    question = await question_review.approve_question(session, vacancy_id, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return QuestionRead.model_validate(question)


@router.post("/{vacancy_id}/questions/approve", response_model=list[QuestionRead])
async def approve_core_questions(
    vacancy_id: uuid.UUID, session: SessionDep, current_user: CurrentUserDep
) -> list[QuestionRead]:
    """Подтверждает ядро вопросов — без этого интервью не запускается."""
    ensure_question_review_allowed(current_user)
    try:
        questions = await question_review.approve_core_questions(session, vacancy_id)
    except QuestionsIncompleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сначала сгенерируйте вопросы на все топики вакансии",
        ) from exc
    if questions is None:
        raise _NOT_FOUND
    return [QuestionRead.model_validate(question) for question in questions]


@router.post("/{vacancy_id}/questions/{question_id}/unapprove", response_model=QuestionRead)
async def unapprove_core_question(
    vacancy_id: uuid.UUID,
    question_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> QuestionRead:
    """Снимает подтверждение с одного core-вопроса."""
    ensure_question_review_allowed(current_user)
    question = await question_review.unapprove_question(session, vacancy_id, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return QuestionRead.model_validate(question)


@router.post("/{vacancy_id}/questions/unapprove", response_model=list[QuestionRead])
async def unapprove_core_questions(
    vacancy_id: uuid.UUID, session: SessionDep, current_user: CurrentUserDep
) -> list[QuestionRead]:
    """Снимает подтверждение со всего ядра — интервью снова блокируется."""
    ensure_question_review_allowed(current_user)
    questions = await question_review.unapprove_core_questions(session, vacancy_id)
    if questions is None:
        raise _NOT_FOUND
    return [QuestionRead.model_validate(question) for question in questions]


@router.get("/{vacancy_id}/asr-dictionary", response_model=AsrDictionaryRead)
async def get_asr_dictionary(vacancy_id: uuid.UUID, session: SessionDep) -> AsrDictionaryRead:
    """Возвращает ASR-словарь вакансии и авто-подсказки терминов из матрицы."""
    vacancy = await vacancy_service.get_vacancy(session, vacancy_id)
    if vacancy is None:
        raise _NOT_FOUND
    return AsrDictionaryRead(
        terms=list(vacancy.asr_terms),
        suggested_terms=vacancy_service.suggest_asr_terms(vacancy),
    )


@router.put("/{vacancy_id}/asr-dictionary", response_model=AsrDictionaryRead)
async def set_asr_dictionary(
    vacancy_id: uuid.UUID, data: AsrDictionaryUpdate, session: SessionDep
) -> AsrDictionaryRead:
    """Сохраняет пользовательский ASR-словарь вакансии."""
    vacancy = await vacancy_service.set_asr_terms(session, vacancy_id, data.terms)
    if vacancy is None:
        raise _NOT_FOUND
    return AsrDictionaryRead(
        terms=list(vacancy.asr_terms),
        suggested_terms=vacancy_service.suggest_asr_terms(vacancy),
    )
