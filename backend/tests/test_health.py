"""Tests for FastAPI health endpoint and settings (TASK-002)."""

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.config import Settings, get_settings
from app.main import create_app


def test_health_returns_ok() -> None:
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_docs_available() -> None:
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower() or "openapi" in response.text.lower()


def test_settings_read_from_env(monkeypatch: MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://localhost:4173,http://example.com",
    )
    settings = Settings()
    assert settings.app_env == "test"
    assert settings.secret_key == "test-secret"
    assert settings.cors_origins == [
        "http://localhost:4173",
        "http://example.com",
    ]
