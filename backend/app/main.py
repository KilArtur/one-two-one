"""Точка входа FastAPI-приложения."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import (
    auth_router,
    candidate_auth_router,
    interview_links_router,
    rbac_router,
    vacancies_router,
)
from app.api.answer_upload import router as answer_upload_router
from app.api.candidate_interview import router as candidate_interview_router
from app.api.candidates import router as candidates_router
from app.api.review_queue import router as review_queue_router
from app.api.topic_assessments import router as topic_assessments_router
from app.config import Settings, get_settings
from app.db import dispose_engine, get_db


class HealthResponse(BaseModel):
    """Ответ health-check."""

    status: str
    app_env: str
    version: str


class DatabaseHealthResponse(BaseModel):
    """Ответ проверки соединения с БД."""

    status: str
    database: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Освобождает пул соединений к БД при остановке сервиса."""
    yield
    await dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Собирает приложение: CORS и системные эндпоинты."""
    provided_settings = settings
    settings = settings or get_settings()

    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    if provided_settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
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

    @app.get("/health/db", tags=["system"])
    async def health_db(
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> DatabaseHealthResponse:
        """Проверка соединения с БД: SELECT 1 через сессию из `get_db`."""
        await session.execute(text("SELECT 1"))
        return DatabaseHealthResponse(status="ok", database="ok")

    app.include_router(vacancies_router)
    app.include_router(auth_router)
    app.include_router(candidate_auth_router)
    app.include_router(candidate_interview_router)
    app.include_router(answer_upload_router)
    app.include_router(interview_links_router)
    app.include_router(rbac_router)
    app.include_router(topic_assessments_router)
    app.include_router(review_queue_router)
    app.include_router(candidates_router)

    return app


app = create_app()
