"""Topic CRUD + R8 validation tests (TASK-012)."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import create_app


def _topic(
    title: str,
    order: int = 0,
    *,
    verifiable_by_interview: bool = True,
) -> dict[str, object]:
    return {
        "title": title,
        "skill_type": "hard",
        "importance": "mandatory",
        "requirement_description": f"Need {title}",
        "depth_expectations": "Hands-on",
        "verifiable_by_interview": verifiable_by_interview,
        "order": order,
    }


def _topics(n: int, prefix: str = "Topic") -> list[dict[str, object]]:
    return [_topic(f"{prefix}-{i}", i) for i in range(1, n + 1)]


def _app_client() -> AsyncClient:
    get_settings.cache_clear()
    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")


@pytest.mark.asyncio
async def test_create_vacancy_with_seven_topics_201() -> None:
    """Шаг 1: добавить 7 топиков — получить 201."""
    async with _app_client() as client:
        response = await client.post(
            "/vacancies",
            json={
                "title": f"Seven-{uuid.uuid4().hex[:8]}",
                "grade": "middle",
                "status": "draft",
                "topics": _topics(7),
            },
        )
    assert response.status_code == 201
    body = response.json()
    assert len(body["topics"]) == 7
    titles = {t["title"] for t in body["topics"]}
    assert titles == {f"Topic-{i}" for i in range(1, 8)}


@pytest.mark.asyncio
async def test_save_fewer_than_five_topics_422() -> None:
    """Шаг 2: попытка сохранить менее 5 топиков — получить 422."""
    async with _app_client() as client:
        created = await client.post(
            "/vacancies",
            json={
                "title": f"R8-{uuid.uuid4().hex[:8]}",
                "grade": "middle",
                "status": "draft",
                "topics": _topics(7),
            },
        )
        assert created.status_code == 201
        vacancy_id = created.json()["id"]

        too_few = await client.patch(
            f"/vacancies/{vacancy_id}",
            json={"topics": _topics(4)},
        )
        assert too_few.status_code == 422

        create_too_few = await client.post(
            "/vacancies",
            json={
                "title": f"TooFew-{uuid.uuid4().hex[:8]}",
                "grade": "junior",
                "topics": _topics(3),
            },
        )
        assert create_too_few.status_code == 422


@pytest.mark.asyncio
async def test_unset_verifiable_by_interview_persists() -> None:
    """Шаг 3: снять verifiable_by_interview — изменение сохраняется."""
    async with _app_client() as client:
        created = await client.post(
            "/vacancies",
            json={
                "title": f"Scope-{uuid.uuid4().hex[:8]}",
                "grade": "middle",
                "status": "draft",
                "topics": _topics(5),
            },
        )
        assert created.status_code == 201
        vacancy = created.json()
        vacancy_id = vacancy["id"]
        topic_id = vacancy["topics"][0]["id"]

        patched = await client.patch(
            f"/vacancies/{vacancy_id}/topics/{topic_id}",
            json={"verifiable_by_interview": False},
        )
        assert patched.status_code == 200
        assert patched.json()["verifiable_by_interview"] is False
        assert patched.json()["id"] == topic_id

        fetched = await client.get(f"/vacancies/{vacancy_id}/topics/{topic_id}")
        assert fetched.status_code == 200
        assert fetched.json()["verifiable_by_interview"] is False

        listed = await client.get(f"/vacancies/{vacancy_id}/topics")
        assert listed.status_code == 200
        by_id = {t["id"]: t for t in listed.json()}
        assert by_id[topic_id]["verifiable_by_interview"] is False


@pytest.mark.asyncio
async def test_topic_create_update_delete() -> None:
    """Создание/редактирование/удаление топика работают."""
    async with _app_client() as client:
        created = await client.post(
            "/vacancies",
            json={
                "title": f"CRUD-{uuid.uuid4().hex[:8]}",
                "grade": "senior",
                "status": "draft",
                "topics": _topics(5, "Base"),
            },
        )
        vacancy_id = created.json()["id"]

        added = await client.post(
            f"/vacancies/{vacancy_id}/topics",
            json=_topic("Extra", order=99, verifiable_by_interview=True),
        )
        assert added.status_code == 201
        topic_id = added.json()["id"]
        assert added.json()["title"] == "Extra"

        updated = await client.patch(
            f"/vacancies/{vacancy_id}/topics/{topic_id}",
            json={"title": "Extra-renamed", "skill_type": "soft"},
        )
        assert updated.status_code == 200
        assert updated.json()["title"] == "Extra-renamed"
        assert updated.json()["skill_type"] == "soft"

        deleted = await client.delete(f"/vacancies/{vacancy_id}/topics/{topic_id}")
        assert deleted.status_code == 204

        missing = await client.get(f"/vacancies/{vacancy_id}/topics/{topic_id}")
        assert missing.status_code == 404

        remaining = await client.get(f"/vacancies/{vacancy_id}/topics")
        assert remaining.status_code == 200
        assert len(remaining.json()) == 5


@pytest.mark.asyncio
async def test_more_than_nine_topics_422() -> None:
    """Р8: больше 9 топиков — 422."""
    async with _app_client() as client:
        response = await client.post(
            "/vacancies",
            json={
                "title": f"TooMany-{uuid.uuid4().hex[:8]}",
                "grade": "middle",
                "topics": _topics(10),
            },
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_active_delete_below_five_422() -> None:
    """Active: удаление топика ниже минимума R8 — 422."""
    async with _app_client() as client:
        created = await client.post(
            "/vacancies",
            json={
                "title": f"ActiveR8-{uuid.uuid4().hex[:8]}",
                "grade": "middle",
                "status": "active",
                "topics": _topics(5),
            },
        )
        vacancy_id = created.json()["id"]
        topic_id = created.json()["topics"][0]["id"]

        deleted = await client.delete(f"/vacancies/{vacancy_id}/topics/{topic_id}")
        assert deleted.status_code == 422
