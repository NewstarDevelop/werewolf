"""Async database connection and session management.

This module provides async database support using SQLAlchemy 2.0 async API.
Use get_async_db() for FastAPI dependency injection in async endpoints.
"""
from typing import AsyncGenerator
import logging

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import settings

logger = logging.getLogger(__name__)

# Determine database driver and pool settings based on URL
_is_sqlite = settings.DATABASE_URL_ASYNC.startswith("sqlite")
# CRITICAL FIX: Only use NullPool for SQLite. For PostgreSQL/MySQL, use default QueuePool
# to avoid connection storms and resource exhaustion in production.
_pool_class = StaticPool if _is_sqlite else None  # None = use default QueuePool

# SQLite-specific connection args
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

# Create async engine
if _pool_class is not None:
    async_engine: AsyncEngine = create_async_engine(
        settings.DATABASE_URL_ASYNC,
        echo=settings.DEBUG,  # Log SQL in debug mode
        poolclass=_pool_class,
        connect_args=_connect_args,
    )
else:
    # Use default QueuePool for non-SQLite databases
    async_engine: AsyncEngine = create_async_engine(
        settings.DATABASE_URL_ASYNC,
        echo=settings.DEBUG,  # Log SQL in debug mode
        connect_args=_connect_args,
    )

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection: Get async database session.

    Callers MUST commit explicitly via ``await db.commit()``.
    Rollback is performed automatically if an exception propagates.
    The session is closed after the request.

    Usage:
        @router.get("/api/rooms")
        async def get_rooms(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(Room))
            ...

        @router.post("/api/rooms")
        async def create_room(db: AsyncSession = Depends(get_async_db)):
            room = Room(...)
            db.add(room)
            await db.commit()
            await notify_users(room.id)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_async_db():
    """Initialize async database (create tables if needed).

    This should be called during application startup for development.
    In production, use Alembic migrations instead.
    """
    _ensure_db_config_logged()

    from app.models.base import Base

    if settings.DEBUG:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Async database tables created (DEBUG mode)")


async def close_async_db():
    """Close async database connections.

    This should be called during application shutdown.
    """
    await async_engine.dispose()
    logger.info("Async database connections closed")


# Log configuration (sanitized to avoid leaking credentials)
def _sanitize_db_url(url: str) -> str:
    """Sanitize database URL to hide password."""
    if "://" not in url:
        return url
    try:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            # Format: scheme://user:password@host/db
            credentials, host_db = rest.split("@", 1)
            if ":" in credentials:
                user, _ = credentials.split(":", 1)
                return f"{scheme}://{user}:***@{host_db}"
        return url
    except Exception:
        return url[:20] + "***"

def _log_db_config():
    """Log database configuration. Called lazily to ensure logging is configured."""
    logger.info(f"Async database configured: {_sanitize_db_url(settings.DATABASE_URL_ASYNC)}")

# Defer logging until first use rather than at import time,
# when the logging system may not yet be configured.
_db_config_logged = False

def _ensure_db_config_logged():
    global _db_config_logged
    if not _db_config_logged:
        _db_config_logged = True
        _log_db_config()
