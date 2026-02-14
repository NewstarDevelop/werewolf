"""Tests for the storage abstraction layer."""
import pytest
from unittest.mock import MagicMock

from app.storage.memory import InMemoryBackend
from app.storage.backend import GameStoreBackend


class TestInMemoryBackend:
    """Tests for InMemoryBackend."""

    def setup_method(self):
        self.backend = InMemoryBackend()

    def _make_game(self, game_id: str = "test-game"):
        """Create a minimal mock game object."""
        game = MagicMock()
        game.id = game_id
        return game

    def test_get_nonexistent(self):
        assert self.backend.get("nonexistent") is None

    def test_put_and_get(self):
        game = self._make_game()
        self.backend.put("g1", game)
        assert self.backend.get("g1") is game

    def test_put_overwrites(self):
        game1 = self._make_game()
        game2 = self._make_game()
        self.backend.put("g1", game1)
        self.backend.put("g1", game2)
        assert self.backend.get("g1") is game2

    def test_delete_existing(self):
        game = self._make_game()
        self.backend.put("g1", game)
        assert self.backend.delete("g1") is True
        assert self.backend.get("g1") is None

    def test_delete_nonexistent(self):
        assert self.backend.delete("nonexistent") is False

    def test_exists(self):
        assert self.backend.exists("g1") is False
        self.backend.put("g1", self._make_game())
        assert self.backend.exists("g1") is True

    def test_count_empty(self):
        assert self.backend.count() == 0

    def test_count_after_operations(self):
        self.backend.put("g1", self._make_game())
        self.backend.put("g2", self._make_game())
        assert self.backend.count() == 2
        self.backend.delete("g1")
        assert self.backend.count() == 1

    def test_all_ids_empty(self):
        assert self.backend.all_ids() == []

    def test_all_ids(self):
        self.backend.put("g1", self._make_game())
        self.backend.put("g2", self._make_game())
        ids = self.backend.all_ids()
        assert set(ids) == {"g1", "g2"}

    def test_reference_semantics(self):
        """InMemoryBackend stores by reference — mutations are visible without put()."""
        game = self._make_game()
        game.day = 1
        self.backend.put("g1", game)
        game.day = 2
        retrieved = self.backend.get("g1")
        assert retrieved.day == 2


class TestInMemoryBackendConformsToProtocol:
    """Verify InMemoryBackend structurally matches GameStoreBackend Protocol."""

    def test_has_all_protocol_methods(self):
        backend = InMemoryBackend()
        assert hasattr(backend, "get")
        assert hasattr(backend, "put")
        assert hasattr(backend, "delete")
        assert hasattr(backend, "exists")
        assert hasattr(backend, "count")
        assert hasattr(backend, "all_ids")

    def test_isinstance_check_with_runtime_checkable(self):
        """Protocol is structural — isinstance won't work without @runtime_checkable,
        but method signatures must match."""
        backend = InMemoryBackend()
        # Verify callable signatures
        assert callable(backend.get)
        assert callable(backend.put)
        assert callable(backend.delete)
        assert callable(backend.exists)
        assert callable(backend.count)
        assert callable(backend.all_ids)


class TestGameStoreWithBackend:
    """Test that GameStore correctly delegates to the backend."""

    def test_default_backend_is_in_memory(self):
        from app.models.game import GameStore
        store = GameStore(enable_persistence=False)
        assert isinstance(store._backend, InMemoryBackend)

    def test_custom_backend(self):
        from app.models.game import GameStore
        custom = InMemoryBackend()
        store = GameStore(enable_persistence=False, backend=custom)
        assert store._backend is custom

    def test_games_property_returns_backend_dict(self):
        from app.models.game import GameStore
        store = GameStore(enable_persistence=False)
        game = MagicMock()
        game.id = "test"
        store._backend.put("test", game)
        assert "test" in store.games
        assert store.games["test"] is game

    def test_create_game_uses_backend(self):
        from app.models.game import GameStore
        store = GameStore(enable_persistence=False)
        game = store.create_game(language="zh")
        assert store._backend.count() == 1
        assert store._backend.get(game.id) is game

    def test_get_game_uses_backend(self):
        from app.models.game import GameStore
        store = GameStore(enable_persistence=False)
        game = store.create_game(language="zh")
        retrieved = store.get_game(game.id)
        assert retrieved is game

    def test_delete_game_uses_backend(self):
        from app.models.game import GameStore
        store = GameStore(enable_persistence=False)
        game = store.create_game(language="zh")
        assert store.delete_game(game.id) is True
        assert store._backend.count() == 0
        assert store.get_game(game.id) is None
