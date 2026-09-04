"""Проверки подключения к БД: зависимость get_db, эндпоинт /health/db и конфиг Alembic."""

import configparser
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.db import get_db
from app.main import create_app

ROOT_DIR = Path(__file__).resolve().parents[1]
VERSIONS_DIR = ROOT_DIR / "backend" / "alembic" / "versions"


class SessionStub:
    """Минимальная async-сессия для проверки DB dependency."""

    def __init__(self) -> None:
        self.executed_statements: list[str] = []

    async def execute(self, statement: object) -> int:
        self.executed_statements.append(str(statement))
        return 1


@pytest.fixture
def session_stub() -> SessionStub:
    return SessionStub()


@pytest.fixture
async def client(session_stub: SessionStub) -> AsyncIterator[httpx.AsyncClient]:
    """Клиент с подменённой DB dependency без реального Postgres/sqlite."""
    app = create_app(Settings(_env_file=None, app_env="testing"))

    async def override_get_db() -> AsyncIterator[SessionStub]:
        yield session_stub

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


def test_database_url_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@db:5432/interviewer")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://user:pass@db:5432/interviewer"


@pytest.mark.anyio
async def test_health_db_executes_select_1(
    client: httpx.AsyncClient,
    session_stub: SessionStub,
) -> None:
    response = await client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert session_stub.executed_statements == ["SELECT 1"]


@pytest.mark.anyio
async def test_get_db_yields_usable_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """`get_db` возвращает новую сессию из фабрики и закрывает её через async with."""

    class SessionContext:
        def __init__(self) -> None:
            self.entered = False
            self.exited = False

        async def __aenter__(self) -> "SessionContext":
            self.entered = True
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            self.exited = True

    created_sessions: list[SessionContext] = []

    def session_factory() -> SessionContext:
        session = SessionContext()
        created_sessions.append(session)
        return session

    monkeypatch.setattr("app.db.session.get_sessionmaker", lambda: session_factory)

    generator = get_db()
    first_session = await anext(generator)

    assert first_session is created_sessions[0]
    assert created_sessions[0].entered is True

    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    assert created_sessions[0].exited is True


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
