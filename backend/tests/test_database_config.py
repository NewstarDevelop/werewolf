"""Tests for database configuration - A1: DATABASE_URL SSOT.

Verifies that the async database module is correctly configured from settings.
"""
import pytest

from app.core.config import settings
from app.core import database_async


class TestDatabaseConfig:
    """Test database configuration consistency."""

    def test_async_engine_url_matches_settings(self):
        """Verify async engine URL matches settings.DATABASE_URL_ASYNC."""
        engine_url = str(database_async.async_engine.url)
        assert engine_url == settings.DATABASE_URL_ASYNC

    def test_sqlite_uses_static_pool(self):
        """Verify SQLite uses StaticPool for async engine."""
        if settings.DATABASE_URL_ASYNC.startswith("sqlite"):
            from sqlalchemy.pool import StaticPool
            assert isinstance(database_async.async_engine.pool, StaticPool)

    def test_session_factory_configured(self):
        """Verify async session factory is properly configured."""
        assert database_async.AsyncSessionLocal is not None

    def test_init_database_creates_tables(self, tmp_path, monkeypatch):
        """Verify init_database() creates tables using a local sync engine."""
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
        monkeypatch.setenv("DATA_DIR", str(tmp_path))

        import importlib
        from app.core import config
        importlib.reload(config)

        from app.init_db import init_database
        init_database()

        # Verify DB file was created
        assert (tmp_path / "test.db").exists()
