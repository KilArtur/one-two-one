"""FastAPI application entrypoint."""

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import router as auth_router
from app.api.questions import router as questions_router
from app.api.vacancies import router as vacancies_router
from app.config import get_settings
from app.db import get_db


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    application = FastAPI(
        title="ИИ-интервьюер",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # В development разрешаем типичные Vite-origin'ы, даже если в .env указан только :5173.
    cors_origins = list(settings.cors_origins)
    if settings.app_env == "development":
        for origin in (
            "http://localhost:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
        ):
            if origin not in cors_origins:
                cors_origins.append(origin)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/db")
    async def health_db(
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> dict[str, str]:
        """Probe DB connectivity via get_db (SELECT 1)."""
        await session.execute(text("SELECT 1"))
        return {"status": "ok"}

    application.include_router(vacancies_router)
    application.include_router(questions_router)
    application.include_router(auth_router)

    return application


app = create_app()
