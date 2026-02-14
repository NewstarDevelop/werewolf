"""Tests for RedisBackend using mock Redis client."""
import json
import pytest
from unittest.mock import MagicMock, patch

from app.storage.redis_backend import RedisBackend


class FakeRedis:
    """Minimal fake Redis client for testing."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def get(self, key: str):
        return self._store.get(key)

    def set(self, key: str, value: str):
        self._store[key] = value

    def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                count += 1
        return count

    def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    def keys(self, pattern: str) -> list[str]:
        import fnmatch
        return [k for k in self._store if fnmatch.fnmatch(k, pattern)]

    def ping(self) -> bool:
        return True


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def backend(fake_redis):
    """Create a RedisBackend with a fake Redis client."""
    with patch("redis.Redis.from_url", return_value=fake_redis):
        rb = RedisBackend("redis://fake:6379/0")
    # Replace the client directly for clarity
    rb._client = fake_redis
    return rb


def _make_game():
    """Create a real Game object for serialization testing."""
    from app.models.game import Game, Player
    from app.schemas.enums import GameStatus, GamePhase, Role
    game = Game(id="test-game-1", language="zh")
    game.status = GameStatus.PLAYING
    game.day = 2
    game.phase = GamePhase.DAY_SPEECH
    game.players[1] = Player(seat_id=1, role=Role.SEER, is_human=True)
    game.players[2] = Player(seat_id=2, role=Role.WEREWOLF, is_human=False)
    return game


class TestRedisBackendOperations:
    """Test RedisBackend CRUD operations with real serialization."""

    def test_get_nonexistent(self, backend):
        assert backend.get("nonexistent") is None

    def test_put_and_get(self, backend):
        game = _make_game()
        backend.put("g1", game)
        retrieved = backend.get("g1")
        assert retrieved is not None
        assert retrieved.id == "test-game-1"
        assert retrieved.day == 2
        assert len(retrieved.players) == 2

    def test_put_serializes_to_json(self, backend, fake_redis):
        game = _make_game()
        backend.put("g1", game)
        raw = fake_redis.get("werewolf:game:g1")
        assert raw is not None
        data = json.loads(raw)
        assert data["id"] == "test-game-1"
        assert data["day"] == 2

    def test_get_returns_new_copy(self, backend):
        """Each get() returns a fresh deserialized copy."""
        game = _make_game()
        backend.put("g1", game)
        copy1 = backend.get("g1")
        copy2 = backend.get("g1")
        assert copy1 is not copy2
        assert copy1.id == copy2.id

    def test_delete_existing(self, backend):
        game = _make_game()
        backend.put("g1", game)
        assert backend.delete("g1") is True
        assert backend.get("g1") is None

    def test_delete_nonexistent(self, backend):
        assert backend.delete("nonexistent") is False

    def test_exists(self, backend):
        assert backend.exists("g1") is False
        backend.put("g1", _make_game())
        assert backend.exists("g1") is True

    def test_count(self, backend):
        assert backend.count() == 0
        backend.put("g1", _make_game())
        backend.put("g2", _make_game())
        assert backend.count() == 2

    def test_all_ids(self, backend):
        backend.put("g1", _make_game())
        backend.put("g2", _make_game())
        ids = backend.all_ids()
        assert set(ids) == {"g1", "g2"}

    def test_ping(self, backend):
        assert backend.ping() is True


class TestRedisBackendRoundTrip:
    """Test full Game serialization round-trip through Redis."""

    def test_player_fields_preserved(self, backend):
        from app.schemas.enums import Role
        game = _make_game()
        game.players[1].verified_players = {2: True}
        game.players[2].teammates = [3]
        game.players[2].wolf_persona = "aggressive"
        backend.put("g1", game)

        retrieved = backend.get("g1")
        assert retrieved.players[1].verified_players == {2: True}
        assert retrieved.players[2].teammates == [3]
        assert retrieved.players[2].wolf_persona == "aggressive"
        assert retrieved.players[1].role == Role.SEER
        assert retrieved.players[1].is_human is True

    def test_game_state_fields_preserved(self, backend):
        from app.schemas.enums import GamePhase
        game = _make_game()
        game.wolf_votes = {2: 1}
        game.day_votes = {1: 2}
        game.speech_order = [1, 2, 3]
        game.pending_deaths = [1]
        game.state_version = 42
        backend.put("g1", game)

        retrieved = backend.get("g1")
        assert retrieved.wolf_votes == {2: 1}
        assert retrieved.day_votes == {1: 2}
        assert retrieved.speech_order == [1, 2, 3]
        assert retrieved.pending_deaths == [1]
        assert retrieved.state_version == 42

    def test_messages_preserved(self, backend):
        from app.schemas.enums import MessageType
        game = _make_game()
        game.add_message(1, "Hello!", MessageType.SPEECH)
        game.add_message(0, "Night falls", MessageType.SYSTEM)
        backend.put("g1", game)

        retrieved = backend.get("g1")
        assert len(retrieved.messages) == 2
        assert retrieved.messages[0].content == "Hello!"
        assert retrieved.messages[1].msg_type == MessageType.SYSTEM


class TestRedisBackendErrorHandling:
    """Test graceful error handling when Redis is unavailable."""

    def test_get_on_error_returns_none(self, backend):
        backend._client = MagicMock()
        backend._client.get.side_effect = ConnectionError("Redis down")
        assert backend.get("g1") is None

    def test_put_on_error_logs(self, backend):
        backend._client = MagicMock()
        backend._client.set.side_effect = ConnectionError("Redis down")
        # Should not raise
        backend.put("g1", _make_game())

    def test_delete_on_error_returns_false(self, backend):
        backend._client = MagicMock()
        backend._client.delete.side_effect = ConnectionError("Redis down")
        assert backend.delete("g1") is False

    def test_ping_on_error_returns_false(self, backend):
        backend._client = MagicMock()
        backend._client.ping.side_effect = ConnectionError("Redis down")
        assert backend.ping() is False


class TestCreateBackendFactory:
    """Test the create_backend factory function."""

    def test_default_is_memory(self):
        from app.storage import create_backend
        from app.storage.memory import InMemoryBackend
        backend = create_backend()
        assert isinstance(backend, InMemoryBackend)

    @patch.dict("os.environ", {"GAME_STORE_BACKEND": "memory"})
    def test_explicit_memory(self):
        from app.storage import create_backend
        from app.storage.memory import InMemoryBackend
        backend = create_backend()
        assert isinstance(backend, InMemoryBackend)

    @patch.dict("os.environ", {"GAME_STORE_BACKEND": "redis"})
    def test_redis_without_url_falls_back(self):
        from app.storage import create_backend
        from app.storage.memory import InMemoryBackend
        # No REDIS_URL set → should fall back to memory
        with patch.dict("os.environ", {"REDIS_URL": ""}):
            backend = create_backend()
        assert isinstance(backend, InMemoryBackend)

    @patch.dict("os.environ", {"GAME_STORE_BACKEND": "unknown_backend"})
    def test_unknown_backend_falls_back(self):
        from app.storage import create_backend
        from app.storage.memory import InMemoryBackend
        backend = create_backend()
        assert isinstance(backend, InMemoryBackend)

    @patch.dict("os.environ", {
        "GAME_STORE_BACKEND": "redis",
        "REDIS_URL": "redis://localhost:6379/0"
    })
    def test_redis_with_url_and_ping_success(self):
        from app.storage import create_backend
        from app.storage.redis_backend import RedisBackend
        fake = FakeRedis()
        with patch("redis.Redis.from_url", return_value=fake):
            backend = create_backend()
        assert isinstance(backend, RedisBackend)

    @patch.dict("os.environ", {
        "GAME_STORE_BACKEND": "redis",
        "REDIS_URL": "redis://localhost:6379/0"
    })
    def test_redis_ping_failure_falls_back(self):
        from app.storage import create_backend
        from app.storage.memory import InMemoryBackend
        fake = MagicMock()
        fake.ping.return_value = False
        with patch("redis.Redis.from_url", return_value=fake):
            backend = create_backend()
        assert isinstance(backend, InMemoryBackend)
