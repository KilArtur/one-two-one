"""Проверки скелета FastAPI: конфиг, /health, CORS, Swagger."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    settings = Settings(_env_file=None, app_env="testing", cors_origins=["http://localhost:5173"])
    return TestClient(create_app(settings))


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')

    settings = Settings(_env_file=None)

    assert settings.app_env == "production"
    assert settings.cors_origins == ["https://app.example.com"]


def test_cors_headers_present(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_openapi_and_docs_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert "/health" in client.get("/openapi.json").json()["paths"]
