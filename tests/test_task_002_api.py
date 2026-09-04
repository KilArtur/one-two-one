"""Проверки скелета FastAPI: конфиг, /health, CORS, Swagger."""

from collections.abc import AsyncIterator

import httpx
import pytest

from app.config import Settings
from app.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(_env_file=None, app_env="testing", cors_origins=["http://localhost:5173"])
    transport = httpx.ASGITransport(app=create_app(settings))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


@pytest.mark.anyio
async def test_health_returns_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')

    settings = Settings(_env_file=None)

    assert settings.app_env == "production"
    assert settings.cors_origins == ["https://app.example.com"]


@pytest.mark.anyio
async def test_cors_headers_present(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


@pytest.mark.anyio
async def test_openapi_and_docs_available(client: httpx.AsyncClient) -> None:
    assert (await client.get("/docs")).status_code == 200
    assert "/health" in (await client.get("/openapi.json")).json()["paths"]
