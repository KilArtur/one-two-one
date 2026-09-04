"""Vacancy and topic CRUD with immutable matrix versioning (M1 / TASK-011–012)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Topic, Vacancy, VacancyStatus
from app.schemas.vacancy import (
    MAX_TOPICS,
    MIN_TOPICS,
    TopicCreate,
    TopicUpdate,
    VacancyCreate,
    VacancyUpdate,
    validate_topic_count,
)


class TopicCountError(ValueError):
    """Raised when a topic mutation would violate R8 (5–9 topics)."""


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


def _topic_to_create(topic: Topic) -> TopicCreate:
    return TopicCreate(
        title=topic.title,
        skill_type=topic.skill_type,
        importance=topic.importance,
        requirement_description=topic.requirement_description,
        depth_expectations=topic.depth_expectations,
        verifiable_by_interview=topic.verifiable_by_interview,
        order=topic.order,
    )


def _topic_models_fingerprint(topics: list[Topic]) -> list[tuple[object, ...]]:
    return _topics_fingerprint([_topic_to_create(t) for t in topics])


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


def _sorted_topics(topics: list[Topic]) -> list[Topic]:
    return sorted(topics, key=lambda t: (t.order, str(t.id)))


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


async def list_topics(
    session: AsyncSession, vacancy_id: uuid.UUID
) -> list[Topic] | None:
    """List topics for a vacancy; None if vacancy missing."""
    vacancy = await get_vacancy(session, vacancy_id)
    if vacancy is None:
        return None
    return _sorted_topics(list(vacancy.topics))


async def get_topic(
    session: AsyncSession,
    vacancy_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> Topic | None:
    """Load a topic belonging to a vacancy snapshot."""
    vacancy = await get_vacancy(session, vacancy_id)
    if vacancy is None:
        return None
    for topic in vacancy.topics:
        if topic.id == topic_id:
            return topic
    return None


async def _apply_matrix(
    session: AsyncSession,
    vacancy: Vacancy,
    topics: list[TopicCreate],
    *,
    allow_partial: bool = False,
) -> Vacancy:
    """Replace topic matrix; version active vacancies."""
    if allow_partial:
        if len(topics) > MAX_TOPICS:
            raise TopicCountError(
                f"Topic count must be {MIN_TOPICS}–{MAX_TOPICS} (R8), "
                f"got {len(topics)}"
            )
    else:
        validate_topic_count(len(topics), allow_empty=False)

    if vacancy.status == VacancyStatus.ACTIVE:
        new_id = uuid.uuid4()
        new_vacancy = Vacancy(
            id=new_id,
            title=vacancy.title,
            grade=vacancy.grade,
            tasks=vacancy.tasks,
            stop_factors=list(vacancy.stop_factors),
            specialist_profile=vacancy.specialist_profile,
            version=vacancy.version + 1,
            status=VacancyStatus.ACTIVE,
            topics=_build_topics(new_id, topics),
        )
        session.add(new_vacancy)
        await session.commit()
        loaded = await get_vacancy(session, new_id)
        assert loaded is not None
        return loaded

    vacancy.topics.clear()
    await session.flush()
    vacancy.topics.extend(_build_topics(vacancy.id, topics))
    await session.commit()
    loaded = await get_vacancy(session, vacancy.id)
    assert loaded is not None
    return loaded


async def create_topic(
    session: AsyncSession,
    vacancy_id: uuid.UUID,
    data: TopicCreate,
) -> tuple[Vacancy, Topic] | None:
    """Append a topic; rejects when resulting count > MAX_TOPICS."""
    vacancy = await get_vacancy(session, vacancy_id)
    if vacancy is None:
        return None

    current = [_topic_to_create(t) for t in _sorted_topics(list(vacancy.topics))]
    if len(current) >= MAX_TOPICS:
        raise TopicCountError(
            f"Topic count must be {MIN_TOPICS}–{MAX_TOPICS} (R8), "
            f"got {len(current) + 1}"
        )
    current.append(data)

    # Draft may grow from 0 toward 5–9; active matrix must stay within R8.
    allow_partial = (
        vacancy.status != VacancyStatus.ACTIVE and len(current) < MIN_TOPICS
    )
    if not allow_partial:
        validate_topic_count(len(current), allow_empty=False)

    if vacancy.status == VacancyStatus.ACTIVE:
        updated = await _apply_matrix(session, vacancy, current)
        created = next(
            t
            for t in _sorted_topics(list(updated.topics))
            if _topic_to_create(t) == data
        )
        return updated, created

    topic = Topic(
        id=uuid.uuid4(),
        vacancy_id=vacancy.id,
        title=data.title,
        skill_type=data.skill_type,
        importance=data.importance,
        requirement_description=data.requirement_description,
        depth_expectations=data.depth_expectations,
        verifiable_by_interview=data.verifiable_by_interview,
        order=data.order,
    )
    vacancy.topics.append(topic)
    await session.commit()
    loaded = await get_vacancy(session, vacancy.id)
    assert loaded is not None
    found = next(t for t in loaded.topics if t.id == topic.id)
    return loaded, found


async def update_topic(
    session: AsyncSession,
    vacancy_id: uuid.UUID,
    topic_id: uuid.UUID,
    data: TopicUpdate,
) -> tuple[Vacancy, Topic] | None:
    """Patch a single topic (incl. verifiable_by_interview / out-of-scope)."""
    vacancy = await get_vacancy(session, vacancy_id)
    if vacancy is None:
        return None

    target = next((t for t in vacancy.topics if t.id == topic_id), None)
    if target is None:
        return None

    payload = data.model_dump(exclude_unset=True)
    if not payload:
        return vacancy, target

    # Active + matrix field change → immutable snapshot with new topic ids.
    if vacancy.status == VacancyStatus.ACTIVE:
        target_index = next(
            i
            for i, topic in enumerate(_sorted_topics(list(vacancy.topics)))
            if topic.id == topic_id
        )
        replacement: list[TopicCreate] = []
        for topic in _sorted_topics(list(vacancy.topics)):
            item = _topic_to_create(topic)
            if topic.id == topic_id:
                item = item.model_copy(update=payload)
            replacement.append(item)
        patched = replacement[target_index]
        updated = await _apply_matrix(session, vacancy, replacement)
        found = next(t for t in updated.topics if _topic_to_create(t) == patched)
        return updated, found

    # Draft: mutate in place so topic id stays stable.
    if "title" in payload:
        target.title = payload["title"]
    if "skill_type" in payload:
        target.skill_type = payload["skill_type"]
    if "importance" in payload:
        target.importance = payload["importance"]
    if "requirement_description" in payload:
        target.requirement_description = payload["requirement_description"]
    if "depth_expectations" in payload:
        target.depth_expectations = payload["depth_expectations"]
    if "verifiable_by_interview" in payload:
        target.verifiable_by_interview = payload["verifiable_by_interview"]
    if "order" in payload:
        target.order = payload["order"]

    await session.commit()
    loaded = await get_vacancy(session, vacancy.id)
    assert loaded is not None
    found = next(t for t in loaded.topics if t.id == topic_id)
    return loaded, found


async def delete_topic(
    session: AsyncSession,
    vacancy_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> Vacancy | None:
    """Remove a topic; R8 rejects counts outside 5–9 (empty draft allowed)."""
    vacancy = await get_vacancy(session, vacancy_id)
    if vacancy is None:
        return None

    target = next((t for t in vacancy.topics if t.id == topic_id), None)
    if target is None:
        return None

    remaining = [
        _topic_to_create(t)
        for t in _sorted_topics(list(vacancy.topics))
        if t.id != topic_id
    ]

    if not remaining:
        if vacancy.status == VacancyStatus.ACTIVE:
            raise TopicCountError(
                f"Topic count must be {MIN_TOPICS}–{MAX_TOPICS} (R8), got 0"
            )
        vacancy.topics.clear()
        await session.flush()
        await session.commit()
        return await get_vacancy(session, vacancy.id)

    allow_partial = (
        vacancy.status != VacancyStatus.ACTIVE and len(remaining) < MIN_TOPICS
    )
    if not allow_partial:
        try:
            validate_topic_count(len(remaining), allow_empty=False)
        except ValueError as exc:
            raise TopicCountError(str(exc)) from exc

    if vacancy.status == VacancyStatus.ACTIVE:
        return await _apply_matrix(session, vacancy, remaining)

    await session.delete(target)
    await session.commit()
    return await get_vacancy(session, vacancy.id)
