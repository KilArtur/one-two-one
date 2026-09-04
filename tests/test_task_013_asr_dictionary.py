"""Пользовательский ASR-словарь на вакансию с авто-подсказкой терминов (TASK-013)."""

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, get_db
from app.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """API-клиент поверх async SQLite in-memory."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    app = create_app(Settings(_env_file=None, app_env="testing"))
    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
    await engine.dispose()


def _topic(title: str, order: int = 0, requirement: str | None = None) -> dict:
    return {
        "title": title,
        "skill_type": "hard",
        "importance": "mandatory",
        "order": order,
        "requirement_description": requirement,
    }


async def _create_vacancy(client: httpx.AsyncClient, topics: list[dict] | None = None) -> dict:
    payload = {"title": "Backend", "grade": "middle", "topics": topics or []}
    return (await client.post("/vacancies", json=payload)).json()


@pytest.mark.anyio
async def test_put_dictionary_then_get_returns_it(client: httpx.AsyncClient) -> None:
    vacancy = await _create_vacancy(client)
    vid = vacancy["id"]

    put = await client.put(
        f"/vacancies/{vid}/asr-dictionary",
        json={"terms": ["ClickHouse", "idempotency"]},
    )
    assert put.status_code == 200
    assert put.json()["terms"] == ["ClickHouse", "idempotency"]

    got = await client.get(f"/vacancies/{vid}/asr-dictionary")
    assert got.status_code == 200
    assert got.json()["terms"] == ["ClickHouse", "idempotency"]


@pytest.mark.anyio
async def test_auto_suggest_from_topics(client: httpx.AsyncClient) -> None:
    vacancy = await _create_vacancy(client, [_topic("Базы данных", 0)])
    vid = vacancy["id"]

    # Шаг 2: создаём топик «Kafka» — термин предлагается автоматически
    await client.post(f"/vacancies/{vid}/topics", json=_topic("Kafka", 1))
    got = await client.get(f"/vacancies/{vid}/asr-dictionary")

    assert "Kafka" in got.json()["suggested_terms"]


@pytest.mark.anyio
async def test_suggest_extracts_terms_from_requirement(client: httpx.AsyncClient) -> None:
    vacancy = await _create_vacancy(
        client,
        [_topic("Стриминг", 0, requirement="Опыт с ClickHouse и потоками данных")],
    )
    got = await client.get(f"/vacancies/{vacancy['id']}/asr-dictionary")
    assert "ClickHouse" in got.json()["suggested_terms"]


@pytest.mark.anyio
async def test_manual_delete_term(client: httpx.AsyncClient) -> None:
    vacancy = await _create_vacancy(client)
    vid = vacancy["id"]

    await client.put(f"/vacancies/{vid}/asr-dictionary", json={"terms": ["Kafka", "Redis"]})
    # Шаг 3: удаляем термин вручную (сохраняем словарь без него)
    updated = await client.put(f"/vacancies/{vid}/asr-dictionary", json={"terms": ["Kafka"]})

    assert updated.json()["terms"] == ["Kafka"]
    got = await client.get(f"/vacancies/{vid}/asr-dictionary")
    assert got.json()["terms"] == ["Kafka"]


@pytest.mark.anyio
async def test_saved_terms_excluded_from_suggestions(client: httpx.AsyncClient) -> None:
    vacancy = await _create_vacancy(client, [_topic("Kafka", 0)])
    vid = vacancy["id"]

    await client.put(f"/vacancies/{vid}/asr-dictionary", json={"terms": ["Kafka"]})
    got = await client.get(f"/vacancies/{vid}/asr-dictionary")

    assert got.json()["terms"] == ["Kafka"]
    assert "Kafka" not in got.json()["suggested_terms"]
