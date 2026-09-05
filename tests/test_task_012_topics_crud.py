"""CRUD топиков вакансии с валидацией 5–9 (Р8) и пометкой «вне зоны интервью» (TASK-012)."""

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


def _topic(title: str, order: int = 0) -> dict:
    return {"title": title, "skill_type": "hard", "importance": "mandatory", "order": order}


async def _create_vacancy(client: httpx.AsyncClient, topics: list[dict] | None = None) -> dict:
    payload = {"title": "Backend", "grade": "middle", "topics": topics or []}
    return (await client.post("/vacancies", json=payload)).json()


@pytest.mark.anyio
async def test_add_seven_topics_returns_201(client: httpx.AsyncClient) -> None:
    vacancy = await _create_vacancy(client)
    vid = vacancy["id"]

    for i in range(7):
        resp = await client.post(f"/vacancies/{vid}/topics", json=_topic(f"Топик {i}", i))
        assert resp.status_code == 201

    read = await client.get(f"/vacancies/{vid}")
    assert len(read.json()["topics"]) == 7


@pytest.mark.anyio
async def test_save_fewer_than_five_returns_422(client: httpx.AsyncClient) -> None:
    vacancy = await _create_vacancy(client)
    resp = await client.put(
        f"/vacancies/{vacancy['id']}/topics",
        json={"topics": [_topic(f"T{i}", i) for i in range(4)]},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_save_more_than_nine_returns_422(client: httpx.AsyncClient) -> None:
    vacancy = await _create_vacancy(client)
    resp = await client.put(
        f"/vacancies/{vacancy['id']}/topics",
        json={"topics": [_topic(f"T{i}", i) for i in range(10)]},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_add_beyond_nine_returns_422(client: httpx.AsyncClient) -> None:
    vacancy = await _create_vacancy(client, [_topic(f"T{i}", i) for i in range(9)])
    resp = await client.post(f"/vacancies/{vacancy['id']}/topics", json=_topic("Десятый", 9))
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_edit_and_delete_topic(client: httpx.AsyncClient) -> None:
    vacancy = await _create_vacancy(client, [_topic("Old", 0)])
    vid = vacancy["id"]
    topic_id = vacancy["topics"][0]["id"]

    edited = await client.patch(f"/vacancies/{vid}/topics/{topic_id}", json={"title": "New"})
    assert edited.status_code == 200
    assert edited.json()["title"] == "New"

    deleted = await client.delete(f"/vacancies/{vid}/topics/{topic_id}")
    assert deleted.status_code == 204

    read = await client.get(f"/vacancies/{vid}")
    assert read.json()["topics"] == []

    missing = await client.delete(f"/vacancies/{vid}/topics/{topic_id}")
    assert missing.status_code == 404


@pytest.mark.anyio
async def test_individual_topic_edit_on_active_returns_409(client: httpx.AsyncClient) -> None:
    vacancy = await _create_vacancy(client, [_topic("A", 0)])
    vid = vacancy["id"]
    await client.patch(f"/vacancies/{vid}", json={"status": "active"})

    resp = await client.post(f"/vacancies/{vid}/topics", json=_topic("B", 1))
    assert resp.status_code == 409
