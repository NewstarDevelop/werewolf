"""Tests for distributed lock implementation."""
import asyncio
import pytest
from unittest.mock import MagicMock, patch

from app.storage.distributed_lock import RedisLock, RedisLockManager


class FakeRedisForLock:
    """Minimal fake Redis client that simulates SET NX EX and Lua eval."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def set(self, key: str, value: str, nx: bool = False, ex: int = None):
        if nx and key in self._store:
            return None  # Key exists, NX fails
        self._store[key] = value
        return True

    def get(self, key: str):
        return self._store.get(key)

    def eval(self, script: str, numkeys: int, *args):
        """Simulate the check-and-delete Lua script."""
        key = args[0]
        token = args[1]
        if self._store.get(key) == token:
            del self._store[key]
            return 1
        return 0

    def delete(self, key: str):
        if key in self._store:
            del self._store[key]
            return 1
        return 0


@pytest.fixture
def fake_redis():
    return FakeRedisForLock()


class TestRedisLock:
    """Test RedisLock acquire/release semantics."""

    @pytest.mark.asyncio
    async def test_acquire_and_release(self, fake_redis):
        lock = RedisLock(fake_redis, "test:lock:1", ttl=10)
        acquired = await lock.acquire()
        assert acquired is True
        assert "test:lock:1" in fake_redis._store

        lock.release()
        assert "test:lock:1" not in fake_redis._store

    @pytest.mark.asyncio
    async def test_acquire_fails_when_held(self, fake_redis):
        lock1 = RedisLock(fake_redis, "test:lock:1", ttl=10, acquire_timeout=0.1)
        lock2 = RedisLock(fake_redis, "test:lock:1", ttl=10, acquire_timeout=0.1)

        await lock1.acquire()
        # lock2 should fail — lock is held
        acquired = await lock2.acquire()
        assert acquired is False

        lock1.release()

    @pytest.mark.asyncio
    async def test_acquire_succeeds_after_release(self, fake_redis):
        lock1 = RedisLock(fake_redis, "test:lock:1", ttl=10)
        lock2 = RedisLock(fake_redis, "test:lock:1", ttl=10, acquire_timeout=0.5)

        await lock1.acquire()
        lock1.release()

        # Now lock2 should succeed
        acquired = await lock2.acquire()
        assert acquired is True
        lock2.release()

    @pytest.mark.asyncio
    async def test_only_holder_can_release(self, fake_redis):
        """A different lock instance cannot release a lock it doesn't hold."""
        lock1 = RedisLock(fake_redis, "test:lock:1", ttl=10)
        lock2 = RedisLock(fake_redis, "test:lock:1", ttl=10)

        await lock1.acquire()
        # lock2 tries to release — should fail (wrong token)
        lock2._token = "wrong-token"
        lock2.release()

        # Lock should still be held by lock1
        assert "test:lock:1" in fake_redis._store
        lock1.release()

    @pytest.mark.asyncio
    async def test_release_without_acquire_is_noop(self, fake_redis):
        lock = RedisLock(fake_redis, "test:lock:1", ttl=10)
        # Should not raise
        lock.release()

    @pytest.mark.asyncio
    async def test_async_context_manager(self, fake_redis):
        lock = RedisLock(fake_redis, "test:lock:1", ttl=10)
        async with lock:
            assert "test:lock:1" in fake_redis._store
        # Released after context
        assert "test:lock:1" not in fake_redis._store

    @pytest.mark.asyncio
    async def test_context_manager_timeout_raises(self, fake_redis):
        lock1 = RedisLock(fake_redis, "test:lock:1", ttl=10)
        await lock1.acquire()

        lock2 = RedisLock(fake_redis, "test:lock:1", ttl=10, acquire_timeout=0.1)
        with pytest.raises(TimeoutError):
            async with lock2:
                pass  # Should not reach here

        lock1.release()

    @pytest.mark.asyncio
    async def test_context_manager_releases_on_exception(self, fake_redis):
        lock = RedisLock(fake_redis, "test:lock:1", ttl=10)
        with pytest.raises(ValueError):
            async with lock:
                assert "test:lock:1" in fake_redis._store
                raise ValueError("test error")
        # Lock should still be released
        assert "test:lock:1" not in fake_redis._store

    @pytest.mark.asyncio
    async def test_redis_error_on_release_is_handled(self, fake_redis):
        lock = RedisLock(fake_redis, "test:lock:1", ttl=10)
        await lock.acquire()
        # Simulate Redis error during release
        lock._client = MagicMock()
        lock._client.eval.side_effect = ConnectionError("Redis down")
        # Should not raise
        lock.release()


class TestRedisLockManager:
    """Test RedisLockManager factory."""

    def test_creates_lock_with_correct_key(self, fake_redis):
        manager = RedisLockManager(fake_redis)
        lock = manager.get_lock("game-123")
        assert lock._key == "werewolf:lock:game-123"

    def test_different_games_get_different_keys(self, fake_redis):
        manager = RedisLockManager(fake_redis)
        lock1 = manager.get_lock("game-1")
        lock2 = manager.get_lock("game-2")
        assert lock1._key != lock2._key

    @pytest.mark.asyncio
    async def test_locks_are_independent(self, fake_redis):
        manager = RedisLockManager(fake_redis)
        lock1 = manager.get_lock("game-1")
        lock2 = manager.get_lock("game-2")

        await lock1.acquire()
        # lock2 for different game should succeed
        acquired = await lock2.acquire()
        assert acquired is True

        lock1.release()
        lock2.release()


class TestGameStoreGetLock:
    """Test GameStore.get_lock integration."""

    def test_memory_backend_returns_asyncio_lock(self):
        from app.models.game import GameStore
        store = GameStore(enable_persistence=False)
        lock = store.get_lock("game-1")
        assert isinstance(lock, asyncio.Lock)

    def test_memory_backend_same_game_same_lock(self):
        from app.models.game import GameStore
        store = GameStore(enable_persistence=False)
        lock1 = store.get_lock("game-1")
        lock2 = store.get_lock("game-1")
        assert lock1 is lock2

    def test_redis_backend_returns_redis_lock(self):
        from app.models.game import GameStore
        from app.storage.redis_backend import RedisBackend
        from unittest.mock import patch

        fake = FakeRedisForLock()
        with patch("redis.Redis.from_url", return_value=fake):
            rb = RedisBackend("redis://fake:6379/0")
        rb._client = fake

        store = GameStore(enable_persistence=False, backend=rb)
        lock = store.get_lock("game-1")
        assert isinstance(lock, RedisLock)

    def test_redis_backend_different_calls_different_lock_instances(self):
        from app.models.game import GameStore
        from app.storage.redis_backend import RedisBackend
        from unittest.mock import patch

        fake = FakeRedisForLock()
        with patch("redis.Redis.from_url", return_value=fake):
            rb = RedisBackend("redis://fake:6379/0")
        rb._client = fake

        store = GameStore(enable_persistence=False, backend=rb)
        lock1 = store.get_lock("game-1")
        lock2 = store.get_lock("game-1")
        # RedisLock creates new instances each time (stateless factory)
        assert lock1 is not lock2
        # But they target the same key
        assert lock1._key == lock2._key
