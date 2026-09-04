"""Точка входа FastAPI-приложения."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import Settings, get_settings


class HealthResponse(BaseModel):
    """Ответ health-check."""

    status: str
    app_env: str
    version: str


def create_app(settings: Settings | None = None) -> FastAPI:
    """Собирает приложение: CORS и системные эндпоинты."""
    settings = settings or get_settings()

    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    async def health() -> HealthResponse:
        """Проверка живости сервиса."""
        return HealthResponse(
            status="ok",
            app_env=settings.app_env,
            version=settings.app_version,
        )

    return app


app = create_app()
