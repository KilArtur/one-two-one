"""Конфигурация сервиса: читается из переменных окружения и `.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
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
    jwt_secret_key: str = ""
    internal_auth_password: str = "change-me"
    jwt_access_token_ttl_seconds: int = 3600
    candidate_jwt_access_token_ttl_seconds: int = 1800

    database_url: str = "postgresql+asyncpg://interviewer:interviewer@localhost:5432/interviewer"
    database_echo: bool = False
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_default_headers: dict[str, str] = Field(default_factory=dict)
    llm_model: str = "gpt-4o"
    llm_fast_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0

    audio_api_key: str = ""
    audio_base_url: str = "https://api.openai.com/v1"
    tts_model: str = "tts-1"
    tts_voice: str = "alloy"
    tts_timeout_seconds: float = Field(default=30.0, gt=0)

    s3_endpoint_url: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket: str = "interviewer-media"
    s3_presigned_url_ttl_seconds: int = 3600
    s3_use_path_style: bool = True


@lru_cache
def get_settings() -> Settings:
    """Возвращает кешированный экземпляр настроек."""
    return Settings()
