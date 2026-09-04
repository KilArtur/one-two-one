"""CRUD-эндпоинты вакансии и топиков с версионированием матрицы (M1) и ASR-словарём."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.vacancy import (
    AsrDictionaryRead,
    AsrDictionaryUpdate,
    TopicRead,
    TopicsReplace,
    TopicUpdate,
    TopicWrite,
    VacancyCreate,
    VacancyRead,
    VacancyUpdate,
)
from app.services import vacancy as vacancy_service
from app.services.vacancy import TopicCountError, VacancyNotDraftError

router = APIRouter(prefix="/vacancies", tags=["vacancies"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")
_TOPIC_COUNT = HTTPException(
    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    detail=f"Число топиков должно быть от {vacancy_service.MIN_TOPICS} "
    f"до {vacancy_service.MAX_TOPICS} (Р8)",
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
    """Редактирует топик черновика (в т.ч. снятие verifiable_by_interview, Р15)."""
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
