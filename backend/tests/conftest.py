"""Pytest configuration and fixtures for backend tests."""
import os
import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment before importing app
os.environ["DEBUG"] = "true"
os.environ["LLM_USE_MOCK"] = "true"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
# Use file-based SQLite for shared access between sync and async engines
os.environ["DATABASE_URL"] = "sqlite:///test_db.sqlite"

from app.models.base import Base
from app.core.database import get_db
from app.core.database_async import get_async_db
from app.main import app


# ============================================================================
# Event Loop Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================

# Use file-based SQLite for both sync and async (shared database)
import tempfile
import atexit

# Create a temporary database file that both engines share
_test_db_path = os.path.join(tempfile.gettempdir(), f"werewolf_test_{os.getpid()}.db")
SYNC_DATABASE_URL = f"sqlite:///{_test_db_path}"
ASYNC_DATABASE_URL = f"sqlite+aiosqlite:///{_test_db_path}"


def _cleanup_test_db():
    """Remove test database file on exit."""
    try:
        if os.path.exists(_test_db_path):
            os.remove(_test_db_path)
    except Exception:
        pass


atexit.register(_cleanup_test_db)

@pytest.fixture(scope="session")
def sync_engine():
    """Create sync SQLite engine for testing."""
    engine = create_engine(
        SYNC_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(sync_engine) -> Generator[Session, None, None]:
    """Create a new database session for a test."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# Async engine for async tests - sync wrapper for use in sync fixtures
# Uses shared database file with sync engine

# Shared async engine instance (created lazily)
_async_engine = None
_async_tables_created = False


def get_test_async_engine():
    """Get or create the shared async engine for testing."""
    global _async_engine, _async_tables_created
    if _async_engine is None:
        _async_engine = create_async_engine(
            ASYNC_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return _async_engine


async def _ensure_async_tables():
    """Ensure tables are created in async engine."""
    global _async_tables_created
    if not _async_tables_created:
        engine = get_test_async_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _async_tables_created = True


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    """Create async SQLite engine for testing."""
    engine = get_test_async_engine()
    await _ensure_async_tables()
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new async database session for a test."""
    async_session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


# ============================================================================
# Application Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_app(db_session, sync_engine) -> FastAPI:
    """Create a test FastAPI application with overridden dependencies."""
    import asyncio

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Ensure async tables exist (run in event loop)
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_ensure_async_tables())
    loop.close()

    # Create async session factory bound to test engine
    test_async_engine = get_test_async_engine()
    test_async_session_factory = async_sessionmaker(
        test_async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_async_db():
        """Override async db to use test async engine."""
        async with test_async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_async_db] = override_get_async_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(test_app) -> Generator[TestClient, None, None]:
    """Create a test client for synchronous tests."""
    with TestClient(test_app) as c:
        yield c


@pytest_asyncio.fixture(scope="function")
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for async tests."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ============================================================================
# Helper Fixtures
# ============================================================================

@pytest.fixture
def test_user_data() -> dict:
    """Sample user data for testing."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "TestPassword123!",
    }


@pytest.fixture
def test_admin_password() -> str:
    """Admin password for testing."""
    os.environ["ADMIN_PASSWORD"] = "test-admin-password"
    return "test-admin-password"
