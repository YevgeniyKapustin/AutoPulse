"""Async SQLAlchemy engine / session helpers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from services.pricer.app.core.config import Settings
from services.pricer.app.models.pricing import Base


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.mysql_dsn,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def create_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
