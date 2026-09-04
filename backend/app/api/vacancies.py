"""Vacancy and topic CRUD endpoints (TASK-011 / TASK-012)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.vacancy import (
    TopicCreate,
    TopicRead,
    TopicUpdate,
    VacancyCreate,
    VacancyRead,
    VacancyUpdate,
)
from app.services import vacancy as vacancy_service
from app.services.vacancy import TopicCountError

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


@router.get("/{vacancy_id}/topics", response_model=list[TopicRead])
async def list_topics(
    vacancy_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[TopicRead]:
    topics = await vacancy_service.list_topics(session, vacancy_id)
    if topics is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return [TopicRead.model_validate(t) for t in topics]


@router.post(
    "/{vacancy_id}/topics",
    response_model=TopicRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_topic(
    vacancy_id: uuid.UUID,
    body: TopicCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TopicRead:
    try:
        result = await vacancy_service.create_topic(session, vacancy_id, body)
    except (TopicCountError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    _vacancy, topic = result
    return TopicRead.model_validate(topic)


@router.get("/{vacancy_id}/topics/{topic_id}", response_model=TopicRead)
async def get_topic(
    vacancy_id: uuid.UUID,
    topic_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TopicRead:
    topic = await vacancy_service.get_topic(session, vacancy_id, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return TopicRead.model_validate(topic)


@router.patch("/{vacancy_id}/topics/{topic_id}", response_model=TopicRead)
async def update_topic(
    vacancy_id: uuid.UUID,
    topic_id: uuid.UUID,
    body: TopicUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TopicRead:
    try:
        result = await vacancy_service.update_topic(
            session, vacancy_id, topic_id, body
        )
    except (TopicCountError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    _vacancy, topic = result
    return TopicRead.model_validate(topic)


@router.delete(
    "/{vacancy_id}/topics/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_topic(
    vacancy_id: uuid.UUID,
    topic_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    try:
        vacancy = await vacancy_service.delete_topic(session, vacancy_id, topic_id)
    except TopicCountError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
