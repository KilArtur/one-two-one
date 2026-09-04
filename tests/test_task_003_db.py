"""Проверки подключения к БД: зависимость get_db, эндпоинт /health/db и конфиг Alembic."""

import configparser
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db import get_engine, get_sessionmaker
from app.main import create_app

ROOT_DIR = Path(__file__).resolve().parents[1]
VERSIONS_DIR = ROOT_DIR / "backend" / "alembic" / "versions"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Клиент поверх временной SQLite-БД: get_db работает без Postgres."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

    settings = Settings(_env_file=None, app_env="testing")
    with TestClient(create_app(settings)) as test_client:
        yield test_client

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


def test_database_url_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@db:5432/interviewer")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://user:pass@db:5432/interviewer"


def test_health_db_executes_select_1(client: TestClient) -> None:
    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_get_db_yields_usable_session(client: TestClient) -> None:
    """Две последовательные проверки используют разные сессии из одного пула."""
    assert client.get("/health/db").status_code == 200
    assert client.get("/health/db").status_code == 200


def test_alembic_config_points_to_backend() -> None:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(ROOT_DIR / "alembic.ini")

    assert parser.get("alembic", "script_location").endswith("backend/alembic")
    assert parser.get("alembic", "prepend_sys_path").endswith("backend")
    assert not parser.has_option("alembic", "sqlalchemy.url")


def test_single_baseline_revision_exists() -> None:
    """Цепочка миграций начинается ровно с одной базовой ревизии."""
    baselines = [
        revision
        for revision in sorted(VERSIONS_DIR.glob("*.py"))
        if "down_revision: str | Sequence[str] | None = None" in revision.read_text()
    ]

    assert len(baselines) == 1
