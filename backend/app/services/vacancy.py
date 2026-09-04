"""CRUD вакансии с версионированием матрицы требований (M1).

Изменение состава топиков активной вакансии создаёт новый иммутабельный снимок
(version+1) с тем же `lineage_id`; предыдущие версии остаются доступными по своему id.
У черновика (draft) состав топиков правится на месте без роста версии.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.topic import Topic
from app.models.vacancy import Vacancy, VacancyStatus
from app.schemas.vacancy import TopicWrite, VacancyCreate, VacancyUpdate


def _build_topics(topics: list[TopicWrite]) -> list[Topic]:
    """Собирает ORM-топики из входных схем."""
    return [
        Topic(
            title=item.title,
            skill_type=item.skill_type,
            importance=item.importance,
            requirement_description=item.requirement_description,
            depth_expectations=item.depth_expectations,
            verifiable_by_interview=item.verifiable_by_interview,
            order=item.order,
        )
        for item in topics
    ]


async def create_vacancy(session: AsyncSession, data: VacancyCreate) -> Vacancy:
    """Создаёт вакансию версии 1 с исходным составом топиков."""
    vacancy = Vacancy(
        id=uuid.uuid4(),
        title=data.title,
        grade=data.grade,
        tasks=data.tasks,
        stop_factors=list(data.stop_factors),
        specialist_profile=data.specialist_profile,
        version=1,
        status=VacancyStatus.DRAFT,
        topics=_build_topics(data.topics),
    )
    vacancy.lineage_id = vacancy.id
    session.add(vacancy)
    await session.commit()
    await session.refresh(vacancy, ["topics"])
    return vacancy


async def get_vacancy(session: AsyncSession, vacancy_id: uuid.UUID) -> Vacancy | None:
    """Возвращает конкретный снимок вакансии по id (или None)."""
    return await session.get(Vacancy, vacancy_id)


async def list_vacancies(session: AsyncSession) -> list[Vacancy]:
    """Возвращает по последней версии каждой логической вакансии (по lineage_id)."""
    latest = (
        select(Vacancy.lineage_id, func.max(Vacancy.version).label("version"))
        .group_by(Vacancy.lineage_id)
        .subquery()
    )
    stmt = (
        select(Vacancy)
        .join(
            latest,
            (Vacancy.lineage_id == latest.c.lineage_id) & (Vacancy.version == latest.c.version),
        )
        .order_by(Vacancy.created_at)
    )
    result = await session.scalars(stmt)
    return list(result.all())


async def update_vacancy(
    session: AsyncSession, vacancy_id: uuid.UUID, data: VacancyUpdate
) -> Vacancy | None:
    """Обновляет скалярные поля вакансии на месте (без версионирования матрицы)."""
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(vacancy, field, value)
    await session.commit()
    await session.refresh(vacancy, ["topics"])
    return vacancy


async def replace_topics(
    session: AsyncSession, vacancy_id: uuid.UUID, topics: list[TopicWrite]
) -> Vacancy | None:
    """Заменяет состав топиков.

    Для активной вакансии создаёт новую версию-снимок (version+1), сохраняя прежнюю
    неизменной; для черновика правит состав на месте.
    """
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None:
        return None

    if vacancy.status != VacancyStatus.ACTIVE:
        vacancy.topics = _build_topics(topics)
        await session.commit()
        await session.refresh(vacancy, ["topics"])
        return vacancy

    snapshot = Vacancy(
        id=uuid.uuid4(),
        lineage_id=vacancy.lineage_id,
        title=vacancy.title,
        grade=vacancy.grade,
        tasks=vacancy.tasks,
        stop_factors=list(vacancy.stop_factors),
        specialist_profile=vacancy.specialist_profile,
        version=vacancy.version + 1,
        status=vacancy.status,
        topics=_build_topics(topics),
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot, ["topics"])
    return snapshot
