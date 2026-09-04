"""CRUD вакансии и топиков с версионированием матрицы (M1) и ASR-словарём.

Изменение состава топиков активной вакансии создаёт новый иммутабельный снимок
(version+1) с тем же `lineage_id`; предыдущие версии остаются доступными по своему id.
У черновика (draft) состав топиков правится на месте без роста версии.

Инвариант Р8: сохранённый состав вакансии — 5–9 топиков. Проверяется при сохранении
состава через `replace_topics`; индивидуальное добавление ограничено только верхней
границей (нельзя превысить 9), чтобы черновик можно было набирать постепенно.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.topic import Topic
from app.models.vacancy import Vacancy, VacancyStatus
from app.schemas.vacancy import TopicUpdate, TopicWrite, VacancyCreate, VacancyUpdate

MIN_TOPICS = 5
MAX_TOPICS = 9

_TERM_RE = re.compile(r"[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9+#.\-]*")


class TopicCountError(Exception):
    """Нарушение диапазона числа топиков Р8 (5–9)."""


class VacancyNotDraftError(Exception):
    """Индивидуальная правка топиков разрешена только для черновика вакансии."""


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
    """Сохраняет состав топиков (5–9 по Р8).

    Для активной вакансии создаёт новую версию-снимок (version+1), сохраняя прежнюю
    неизменной; для черновика правит состав на месте.
    """
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None:
        return None
    if not MIN_TOPICS <= len(topics) <= MAX_TOPICS:
        raise TopicCountError

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
        asr_terms=list(vacancy.asr_terms),
        version=vacancy.version + 1,
        status=vacancy.status,
        topics=_build_topics(topics),
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot, ["topics"])
    return snapshot


async def add_topic(
    session: AsyncSession, vacancy_id: uuid.UUID, data: TopicWrite
) -> Topic | None:
    """Добавляет один топик в черновик вакансии (верхняя граница Р8 — не больше 9)."""
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None:
        return None
    if vacancy.status != VacancyStatus.DRAFT:
        raise VacancyNotDraftError
    if len(vacancy.topics) + 1 > MAX_TOPICS:
        raise TopicCountError
    topic = _build_topics([data])[0]
    topic.vacancy_id = vacancy.id
    session.add(topic)
    await session.commit()
    await session.refresh(topic)
    return topic


async def update_topic(
    session: AsyncSession,
    vacancy_id: uuid.UUID,
    topic_id: uuid.UUID,
    data: TopicUpdate,
) -> Topic | None:
    """Редактирует топик черновика (в т.ч. пометку «вне зоны интервью», Р15)."""
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None:
        return None
    if vacancy.status != VacancyStatus.DRAFT:
        raise VacancyNotDraftError
    topic = next((item for item in vacancy.topics if item.id == topic_id), None)
    if topic is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(topic, field, value)
    await session.commit()
    await session.refresh(topic)
    return topic


async def delete_topic(
    session: AsyncSession, vacancy_id: uuid.UUID, topic_id: uuid.UUID
) -> bool | None:
    """Удаляет топик из черновика вакансии."""
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None:
        return None
    if vacancy.status != VacancyStatus.DRAFT:
        raise VacancyNotDraftError
    topic = next((item for item in vacancy.topics if item.id == topic_id), None)
    if topic is None:
        return False
    await session.delete(topic)
    await session.commit()
    return True


def suggest_asr_terms(vacancy: Vacancy) -> list[str]:
    """Предлагает термины для ASR-словаря из матрицы требований (Р8/ASR).

    Собирает названия топиков и заметные технические токены из их описаний,
    исключая уже сохранённые в словаре термины.
    """
    seen = {term.lower() for term in vacancy.asr_terms}
    suggestions: list[str] = []
    for topic in sorted(vacancy.topics, key=lambda item: item.order):
        candidates = [topic.title]
        if topic.requirement_description:
            candidates.extend(
                token
                for token in _TERM_RE.findall(topic.requirement_description)
                if len(token) >= 2 and any(char.isupper() for char in token)
            )
        for candidate in candidates:
            key = candidate.lower()
            if key not in seen:
                seen.add(key)
                suggestions.append(candidate)
    return suggestions


async def set_asr_terms(
    session: AsyncSession, vacancy_id: uuid.UUID, terms: list[str]
) -> Vacancy | None:
    """Сохраняет пользовательский ASR-словарь вакансии (ручное редактирование)."""
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None:
        return None
    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        cleaned = term.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            deduped.append(cleaned)
    vacancy.asr_terms = deduped
    await session.commit()
    await session.refresh(vacancy, ["topics"])
    return vacancy
