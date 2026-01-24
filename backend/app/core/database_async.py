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
    Dependency injection: Get async database session with auto-commit.

    Usage:
        @router.get("/api/rooms")
        async def get_rooms(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(Room))
            ...

    The session is automatically closed after the request.
    Rollback is performed if an exception occurs.

    IMPORTANT: Auto-commit on success is convenient but has trade-offs:
    - Pros: Less boilerplate, works well for simple CRUD operations
    - Cons: External side effects (WebSocket, notifications) may execute before commit,
            leading to consistency issues if commit fails

    BEST PRACTICE for operations with external side effects:
    1. Use get_async_db_no_autocommit() instead for explicit control
    2. Perform all DB operations first
    3. Call await db.commit() explicitly
    4. Only trigger external side effects (WebSocket, notifications) AFTER successful commit

    Example:
        async def create_room(db: AsyncSession = Depends(get_async_db_no_autocommit)):
            room = Room(...)
            db.add(room)
            await db.commit()  # Explicit commit
            # Only send notifications after commit succeeds
            await notify_users(room.id)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_async_db_no_autocommit() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection: Get async database session WITHOUT auto-commit.

    Use this when you need explicit transaction control, especially when:
    - Performing operations with external side effects (WebSocket, notifications)
    - Need to ensure side effects only happen after successful commit
    - Require fine-grained transaction boundaries

    Usage:
        @router.post("/api/rooms")
        async def create_room(db: AsyncSession = Depends(get_async_db_no_autocommit)):
            room = Room(...)
            db.add(room)
            await db.commit()  # Must commit explicitly
            # Side effects only after commit
            await notify_users(room.id)

    The session is automatically closed after the request.
    Rollback is performed if an exception occurs.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # No auto-commit - caller must commit explicitly
        except Exception:
            await session.rollback()
            raise


async def init_async_db():
    """Initialize async database (create tables if needed).

    This should be called during application startup for development.
    In production, use Alembic migrations instead.
    """
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

logger.info(f"Async database configured: {_sanitize_db_url(settings.DATABASE_URL_ASYNC)}")
