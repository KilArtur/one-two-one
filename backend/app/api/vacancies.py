"""CRUD-эндпоинты вакансии с версионированием матрицы требований (M1)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.vacancy import (
    TopicsReplace,
    VacancyCreate,
    VacancyRead,
    VacancyUpdate,
)
from app.services import vacancy as vacancy_service

router = APIRouter(prefix="/vacancies", tags=["vacancies"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")
    return VacancyRead.model_validate(vacancy)


@router.patch("/{vacancy_id}", response_model=VacancyRead)
async def update_vacancy(
    vacancy_id: uuid.UUID, data: VacancyUpdate, session: SessionDep
) -> VacancyRead:
    """Обновляет скалярные поля вакансии на месте."""
    vacancy = await vacancy_service.update_vacancy(session, vacancy_id, data)
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")
    return VacancyRead.model_validate(vacancy)


@router.put("/{vacancy_id}/topics", response_model=VacancyRead)
async def replace_topics(
    vacancy_id: uuid.UUID, data: TopicsReplace, session: SessionDep
) -> VacancyRead:
    """Заменяет состав топиков; для активной вакансии создаёт новую версию-снимок."""
    vacancy = await vacancy_service.replace_topics(session, vacancy_id, data.topics)
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")
    return VacancyRead.model_validate(vacancy)
