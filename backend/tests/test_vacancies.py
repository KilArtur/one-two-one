"""Vacancy CRUD + matrix versioning tests (TASK-011)."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import create_app


def _topic(title: str, order: int = 0) -> dict[str, object]:
    return {
        "title": title,
        "skill_type": "hard",
        "importance": "mandatory",
        "requirement_description": f"Need {title}",
        "depth_expectations": "Hands-on",
        "verifiable_by_interview": True,
        "order": order,
    }


def _topics(n: int, prefix: str = "Topic") -> list[dict[str, object]]:
    return [_topic(f"{prefix}-{i}", i) for i in range(1, n + 1)]


def _app_client() -> AsyncClient:
    get_settings.cache_clear()
    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")


@pytest.mark.asyncio
async def test_create_vacancy_returns_201() -> None:
    """Шаг 1: POST вакансию — получить 201."""
    async with _app_client() as client:
        response = await client.post(
            "/vacancies",
            json={
                "title": f"Backend-{uuid.uuid4().hex[:8]}",
                "grade": "middle",
                "tasks": "Build APIs",
                "stop_factors": ["no Python"],
                "specialist_profile": "Python",
                "status": "active",
                "topics": _topics(5, "Core"),
            },
        )
    assert response.status_code == 201
    body = response.json()
    assert body["version"] == 1
    assert body["status"] == "active"
    assert len(body["topics"]) == 5
    assert uuid.UUID(body["id"])


@pytest.mark.asyncio
async def test_list_and_get_vacancy() -> None:
    """create/read/list вакансии работают."""
    title = f"List-{uuid.uuid4().hex[:8]}"
    async with _app_client() as client:
        created = await client.post(
            "/vacancies",
            json={"title": title, "grade": "junior", "topics": _topics(5)},
        )
        assert created.status_code == 201
        vacancy_id = created.json()["id"]

        listed = await client.get("/vacancies")
        assert listed.status_code == 200
        assert any(v["id"] == vacancy_id for v in listed.json())

        fetched = await client.get(f"/vacancies/{vacancy_id}")
        assert fetched.status_code == 200
        assert fetched.json()["title"] == title
        assert fetched.json()["version"] == 1


@pytest.mark.asyncio
async def test_active_topic_change_creates_version_snapshot() -> None:
    """Шаг 2–3: смена топиков active → version=2; старая версия по id доступна."""
    async with _app_client() as client:
        created = await client.post(
            "/vacancies",
            json={
                "title": f"Versioned-{uuid.uuid4().hex[:8]}",
                "grade": "senior",
                "status": "active",
                "topics": _topics(5, "V1"),
            },
        )
        assert created.status_code == 201
        old = created.json()
        old_id = old["id"]
        assert old["version"] == 1

        updated = await client.patch(
            f"/vacancies/{old_id}",
            json={"topics": _topics(6, "V2")},
        )
        assert updated.status_code == 200
        new = updated.json()
        assert new["version"] == 2
        assert new["id"] != old_id
        assert len(new["topics"]) == 6

        new_get = await client.get(f"/vacancies/{new['id']}")
        assert new_get.status_code == 200
        assert new_get.json()["version"] == 2

        old_get = await client.get(f"/vacancies/{old_id}")
        assert old_get.status_code == 200
        old_body = old_get.json()
        assert old_body["version"] == 1
        assert len(old_body["topics"]) == 5


@pytest.mark.asyncio
async def test_draft_topic_change_mutates_in_place() -> None:
    """Draft: смена топиков без инкремента version."""
    async with _app_client() as client:
        created = await client.post(
            "/vacancies",
            json={
                "title": f"Draft-{uuid.uuid4().hex[:8]}",
                "grade": "middle+",
                "status": "draft",
                "topics": _topics(5, "Draft"),
            },
        )
        vacancy_id = created.json()["id"]

        updated = await client.patch(
            f"/vacancies/{vacancy_id}",
            json={"topics": _topics(6, "Draft2")},
        )
    assert updated.status_code == 200
    body = updated.json()
    assert body["id"] == vacancy_id
    assert body["version"] == 1
    assert len(body["topics"]) == 6


@pytest.mark.asyncio
async def test_metadata_update_does_not_bump_version() -> None:
    """Metadata-only update на active не создаёт новую версию."""
    async with _app_client() as client:
        created = await client.post(
            "/vacancies",
            json={
                "title": f"Meta-{uuid.uuid4().hex[:8]}",
                "grade": "middle",
                "status": "active",
                "topics": _topics(5),
            },
        )
        vacancy_id = created.json()["id"]

        updated = await client.patch(
            f"/vacancies/{vacancy_id}",
            json={"title": "Renamed vacancy", "tasks": "New tasks"},
        )
    assert updated.status_code == 200
    body = updated.json()
    assert body["id"] == vacancy_id
    assert body["version"] == 1
    assert body["title"] == "Renamed vacancy"


@pytest.mark.asyncio
async def test_get_missing_vacancy_404() -> None:
    async with _app_client() as client:
        response = await client.get(f"/vacancies/{uuid.uuid4()}")
    assert response.status_code == 404
