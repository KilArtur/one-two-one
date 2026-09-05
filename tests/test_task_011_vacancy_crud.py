"""CRUD вакансии с версионированием матрицы требований (M1, TASK-011)."""

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
    """API-клиент поверх async SQLite in-memory с подменённой сессией."""
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


def _payload(title: str = "Backend инженер") -> dict:
    return {
        "title": title,
        "grade": "middle+",
        "tasks": "Разработка сервисов",
        "specialist_profile": "Ищем сильного бэкендера",
        "topics": [
            {"title": "Python", "skill_type": "hard", "importance": "mandatory", "order": 0},
            {"title": "PostgreSQL", "skill_type": "hard", "importance": "desired", "order": 1},
        ],
    }


@pytest.mark.anyio
async def test_create_returns_201_version_1(client: httpx.AsyncClient) -> None:
    response = await client.post("/vacancies", json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["version"] == 1
    assert body["status"] == "draft"
    assert body["lineage_id"] == body["id"]
    assert len(body["topics"]) == 2
    assert body["grade"] == "middle+"


@pytest.mark.anyio
async def test_read_and_list(client: httpx.AsyncClient) -> None:
    created = (await client.post("/vacancies", json=_payload("Вакансия A"))).json()
    await client.post("/vacancies", json=_payload("Вакансия B"))

    single = await client.get(f"/vacancies/{created['id']}")
    assert single.status_code == 200
    assert single.json()["title"] == "Вакансия A"

    listing = await client.get("/vacancies")
    assert listing.status_code == 200
    titles = {item["title"] for item in listing.json()}
    assert {"Вакансия A", "Вакансия B"} <= titles

    missing = await client.get("/vacancies/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404


@pytest.mark.anyio
async def test_active_topic_change_creates_new_version_snapshot(client: httpx.AsyncClient) -> None:
    created = (await client.post("/vacancies", json=_payload())).json()
    vacancy_id = created["id"]

    activated = await client.patch(f"/vacancies/{vacancy_id}", json={"status": "active"})
    assert activated.status_code == 200
    assert activated.json()["version"] == 1

    new_topics = {
        "topics": [
            {"title": "Python", "skill_type": "hard", "importance": "mandatory", "order": 0},
            {"title": "Kafka", "skill_type": "hard", "importance": "mandatory", "order": 1},
            {"title": "Docker", "skill_type": "hard", "importance": "desired", "order": 2},
            {"title": "Redis", "skill_type": "hard", "importance": "desired", "order": 3},
            {"title": "gRPC", "skill_type": "hard", "importance": "desired", "order": 4},
        ]
    }
    replaced = await client.put(f"/vacancies/{vacancy_id}/topics", json=new_topics)
    assert replaced.status_code == 200
    new_version = replaced.json()

    # Шаг 2: новая версия матрицы = 2, тот же lineage_id
    assert new_version["version"] == 2
    assert new_version["lineage_id"] == created["lineage_id"]
    assert new_version["id"] != vacancy_id
    assert {t["title"] for t in new_version["topics"]} == {
        "Python",
        "Kafka",
        "Docker",
        "Redis",
        "gRPC",
    }

    # Шаг 3: прежняя версия остаётся доступной по своему id — иммутабельный снимок
    old = await client.get(f"/vacancies/{vacancy_id}")
    assert old.status_code == 200
    assert old.json()["version"] == 1
    assert {t["title"] for t in old.json()["topics"]} == {"Python", "PostgreSQL"}

    # Список отдаёт только последнюю версию логической вакансии
    listing = (await client.get("/vacancies")).json()
    versions = {item["id"]: item["version"] for item in listing}
    assert versions == {new_version["id"]: 2}


@pytest.mark.anyio
async def test_draft_topic_change_edits_in_place(client: httpx.AsyncClient) -> None:
    created = (await client.post("/vacancies", json=_payload())).json()
    vacancy_id = created["id"]

    replaced = await client.put(
        f"/vacancies/{vacancy_id}/topics",
        json={
            "topics": [
                {"title": "Go", "skill_type": "hard", "importance": "mandatory", "order": 0},
                {"title": "gRPC", "skill_type": "hard", "importance": "desired", "order": 1},
                {"title": "Kafka", "skill_type": "hard", "importance": "desired", "order": 2},
                {"title": "Redis", "skill_type": "hard", "importance": "desired", "order": 3},
                {"title": "Docker", "skill_type": "hard", "importance": "desired", "order": 4},
            ]
        },
    )
    assert replaced.status_code == 200
    body = replaced.json()
    assert body["version"] == 1
    assert body["id"] == vacancy_id
    assert {t["title"] for t in body["topics"]} == {"Go", "gRPC", "Kafka", "Redis", "Docker"}


@pytest.mark.anyio
async def test_update_scalar_fields_keeps_version(client: httpx.AsyncClient) -> None:
    created = (await client.post("/vacancies", json=_payload())).json()
    vacancy_id = created["id"]

    updated = await client.patch(
        f"/vacancies/{vacancy_id}",
        json={"title": "Senior Backend", "grade": "senior"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["title"] == "Senior Backend"
    assert body["grade"] == "senior"
    assert body["version"] == 1


@pytest.mark.anyio
async def test_delete_vacancy_removes_all_lineage_versions(client: httpx.AsyncClient) -> None:
    created = (await client.post("/vacancies", json=_payload())).json()
    vacancy_id = created["id"]
    await client.patch(f"/vacancies/{vacancy_id}", json={"status": "active"})
    snapshot = (
        await client.put(
            f"/vacancies/{vacancy_id}/topics",
            json={
                "topics": [
                    {"title": "Python", "skill_type": "hard", "importance": "mandatory", "order": 0},
                    {"title": "Kafka", "skill_type": "hard", "importance": "mandatory", "order": 1},
                    {"title": "Docker", "skill_type": "hard", "importance": "desired", "order": 2},
                    {"title": "Redis", "skill_type": "hard", "importance": "desired", "order": 3},
                    {"title": "gRPC", "skill_type": "hard", "importance": "desired", "order": 4},
                ]
            },
        )
    ).json()

    deleted = await client.delete(f"/vacancies/{snapshot['id']}")
    assert deleted.status_code == 204
    assert (await client.get(f"/vacancies/{vacancy_id}")).status_code == 404
    assert (await client.get(f"/vacancies/{snapshot['id']}")).status_code == 404
    assert (await client.get("/vacancies")).json() == []
    missing = await client.delete("/vacancies/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
