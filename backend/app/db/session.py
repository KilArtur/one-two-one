"""Асинхронное подключение к PostgreSQL и зависимость сессии для FastAPI."""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Возвращает единый async-движок приложения."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Возвращает фабрику async-сессий."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Зависимость FastAPI: сессия БД на время запроса."""
    async with get_sessionmaker()() as session:
        yield session


async def dispose_engine() -> None:
    """Закрывает пул соединений и сбрасывает кеши движка и фабрики сессий."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()
