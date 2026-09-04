"""Application settings loaded from environment / .env."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values come from env vars or `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    secret_key: str = "change-me"
    database_url: str = (
        "postgresql+asyncpg://interviewer:interviewer@localhost:5433/interviewer"
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:3000",
        ]
    )

    # LLM via OpenAI-compatible protocol (OpenRouter / local / other)
    openai_api_key: str = ""
    openai_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "qwen/qwen3-next-80b-a3b-instruct"
    llm_fast_model: str = "qwen/qwen3-30b-a3b-instruct-2507"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        """Allow comma-separated CORS_ORIGINS in .env."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
