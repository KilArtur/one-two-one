"""FastAPI application entrypoint."""

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
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

    return application


app = create_app()
