"""Database engine, session management, and initialization."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from job_search_agent.config import get_settings
from job_search_agent.database.models import Base

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {}
        if "sqlite" in settings.database_url:
            connect_args["check_same_thread"] = False

        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            connect_args=connect_args,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncSession:
    """Create a new async session."""
    factory = get_session_factory()
    return factory()


async def init_db() -> None:
    """Create all tables (development convenience — use Alembic in production)."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the engine."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
