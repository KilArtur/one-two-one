"""Vacancy CRUD with immutable matrix versioning (M1 / TASK-011)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Topic, Vacancy, VacancyStatus
from app.schemas.vacancy import TopicCreate, VacancyCreate, VacancyUpdate


def _topics_fingerprint(topics: list[TopicCreate]) -> list[tuple[object, ...]]:
    """Stable comparable signature of a topic matrix (order-sensitive)."""
    return [
        (
            t.title,
            t.skill_type.value,
            t.importance.value,
            t.requirement_description,
            t.depth_expectations,
            t.verifiable_by_interview,
            t.order,
        )
        for t in topics
    ]


def _topic_models_fingerprint(topics: list[Topic]) -> list[tuple[object, ...]]:
    return _topics_fingerprint(
        [
            TopicCreate(
                title=t.title,
                skill_type=t.skill_type,
                importance=t.importance,
                requirement_description=t.requirement_description,
                depth_expectations=t.depth_expectations,
                verifiable_by_interview=t.verifiable_by_interview,
                order=t.order,
            )
            for t in topics
        ]
    )


def _build_topics(vacancy_id: uuid.UUID, topics: list[TopicCreate]) -> list[Topic]:
    return [
        Topic(
            id=uuid.uuid4(),
            vacancy_id=vacancy_id,
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
    """Insert a new vacancy at version=1 with optional topics."""
    vacancy_id = uuid.uuid4()
    vacancy = Vacancy(
        id=vacancy_id,
        title=data.title,
        grade=data.grade,
        tasks=data.tasks,
        stop_factors=list(data.stop_factors),
        specialist_profile=data.specialist_profile,
        version=1,
        status=data.status,
        topics=_build_topics(vacancy_id, data.topics),
    )
    session.add(vacancy)
    await session.commit()
    loaded = await get_vacancy(session, vacancy_id)
    assert loaded is not None
    return loaded


async def list_vacancies(session: AsyncSession) -> list[Vacancy]:
    """Return all vacancies with topics, newest version first within title."""
    result = await session.execute(
        select(Vacancy)
        .options(selectinload(Vacancy.topics))
        .order_by(Vacancy.title, Vacancy.version.desc())
    )
    return list(result.scalars().unique())


async def get_vacancy(session: AsyncSession, vacancy_id: uuid.UUID) -> Vacancy | None:
    """Load a vacancy snapshot by id (any version)."""
    result = await session.execute(
        select(Vacancy)
        .where(Vacancy.id == vacancy_id)
        .options(selectinload(Vacancy.topics))
    )
    return result.scalar_one_or_none()


async def update_vacancy(
    session: AsyncSession,
    vacancy_id: uuid.UUID,
    data: VacancyUpdate,
) -> Vacancy | None:
    """Update vacancy fields; topic changes on active create version+1 snapshot."""
    vacancy = await get_vacancy(session, vacancy_id)
    if vacancy is None:
        return None

    payload = data.model_dump(exclude_unset=True)
    topics_payload: list[TopicCreate] | None = data.topics
    matrix_changing = topics_payload is not None and _topics_fingerprint(
        topics_payload
    ) != _topic_models_fingerprint(list(vacancy.topics))

    # Active + matrix change → immutable snapshot: new row, old id stays readable.
    if matrix_changing and vacancy.status == VacancyStatus.ACTIVE:
        new_id = uuid.uuid4()
        new_vacancy = Vacancy(
            id=new_id,
            title=payload.get("title", vacancy.title),
            grade=payload.get("grade", vacancy.grade),
            tasks=payload.get("tasks", vacancy.tasks),
            stop_factors=list(payload.get("stop_factors", vacancy.stop_factors)),
            specialist_profile=payload.get(
                "specialist_profile",
                vacancy.specialist_profile,
            ),
            version=vacancy.version + 1,
            status=payload.get("status", VacancyStatus.ACTIVE),
            topics=_build_topics(new_id, topics_payload or []),
        )
        session.add(new_vacancy)
        await session.commit()
        return await get_vacancy(session, new_id)

    if "title" in payload:
        vacancy.title = payload["title"]
    if "grade" in payload:
        vacancy.grade = payload["grade"]
    if "tasks" in payload:
        vacancy.tasks = payload["tasks"]
    if "stop_factors" in payload:
        vacancy.stop_factors = list(payload["stop_factors"])
    if "specialist_profile" in payload:
        vacancy.specialist_profile = payload["specialist_profile"]
    if "status" in payload:
        vacancy.status = payload["status"]

    if matrix_changing and topics_payload is not None:
        vacancy.topics.clear()
        await session.flush()
        vacancy.topics.extend(_build_topics(vacancy.id, topics_payload))

    await session.commit()
    return await get_vacancy(session, vacancy.id)
