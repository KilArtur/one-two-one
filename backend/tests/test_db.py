"""Tests for PostgreSQL session and /health/db (TASK-003)."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.main import create_app


def test_settings_include_database_url(monkeypatch: MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5433/testdb",
    )
    settings = Settings()
    assert settings.database_url == (
        "postgresql+asyncpg://u:p@localhost:5433/testdb"
    )


def test_health_db_with_overridden_session() -> None:
    """Wire get_db into FastAPI without a live database."""
    get_settings.cache_clear()
    application = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock(return_value=MagicMock())
        yield session

    application.dependency_overrides[get_db] = override_get_db
    client = TestClient(application)
    response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_real_db_select_one() -> None:
    """Integration: live Postgres via DATABASE_URL (docker compose)."""
    get_settings.cache_clear()
    from app.db import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_health_db_live() -> None:
    """Integration: GET /health/db returns 200 against live Postgres."""
    get_settings.cache_clear()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
