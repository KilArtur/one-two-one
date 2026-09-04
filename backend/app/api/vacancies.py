"""Vacancy CRUD endpoints (TASK-011)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.vacancy import VacancyCreate, VacancyRead, VacancyUpdate
from app.services import vacancy as vacancy_service

router = APIRouter(prefix="/vacancies", tags=["vacancies"])


@router.post("", response_model=VacancyRead, status_code=status.HTTP_201_CREATED)
async def create_vacancy(
    body: VacancyCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VacancyRead:
    vacancy = await vacancy_service.create_vacancy(session, body)
    return VacancyRead.model_validate(vacancy)


@router.get("", response_model=list[VacancyRead])
async def list_vacancies(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[VacancyRead]:
    vacancies = await vacancy_service.list_vacancies(session)
    return [VacancyRead.model_validate(v) for v in vacancies]


@router.get("/{vacancy_id}", response_model=VacancyRead)
async def get_vacancy(
    vacancy_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VacancyRead:
    vacancy = await vacancy_service.get_vacancy(session, vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return VacancyRead.model_validate(vacancy)


@router.patch("/{vacancy_id}", response_model=VacancyRead)
async def update_vacancy(
    vacancy_id: uuid.UUID,
    body: VacancyUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VacancyRead:
    vacancy = await vacancy_service.update_vacancy(session, vacancy_id, body)
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return VacancyRead.model_validate(vacancy)
