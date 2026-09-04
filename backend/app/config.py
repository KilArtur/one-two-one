"""Конфигурация сервиса: читается из переменных окружения и `.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Interviewer API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]

    database_url: str = "postgresql+asyncpg://interviewer:interviewer@localhost:5432/interviewer"
    database_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    """Возвращает кешированный экземпляр настроек."""
    return Settings()
