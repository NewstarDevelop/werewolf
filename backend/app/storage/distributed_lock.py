"""Distributed lock implementation using Redis.

Provides a Redis-based lock that works across multiple process instances,
replacing asyncio.Lock for multi-instance deployments.

Uses Redis SET NX with automatic expiry to prevent deadlocks.
Compatible with `async with` context manager (same as asyncio.Lock).
"""

import asyncio
import logging
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

# Default lock TTL — auto-releases if holder crashes
_DEFAULT_LOCK_TTL_SECONDS = 30
# Retry interval when waiting to acquire lock
_RETRY_INTERVAL_SECONDS = 0.05
# Maximum time to wait for lock acquisition
_DEFAULT_ACQUIRE_TIMEOUT_SECONDS = 10


class RedisLock:
    """Redis-based distributed lock compatible with `async with`.

    Uses SET NX EX pattern for atomic lock acquisition with automatic expiry.
    Each lock instance has a unique token to ensure only the holder can release.

    Usage:
        lock = RedisLock(redis_client, "werewolf:lock:game-id")
        async with lock:
            # critical section
    """

    def __init__(
        self,
        redis_client,
        key: str,
        ttl: int = _DEFAULT_LOCK_TTL_SECONDS,
        acquire_timeout: float = _DEFAULT_ACQUIRE_TIMEOUT_SECONDS,
    ):
        self._client = redis_client
        self._key = key
        self._ttl = ttl
        self._acquire_timeout = acquire_timeout
        self._token: Optional[str] = None

    async def acquire(self) -> bool:
        """Attempt to acquire the lock within the timeout period.

        Returns:
            True if lock was acquired, False if timed out.
        """
        token = str(uuid.uuid4())
        deadline = time.monotonic() + self._acquire_timeout

        while time.monotonic() < deadline:
            # SET key token NX EX ttl — atomic acquire with expiry
            acquired = self._client.set(
                self._key, token, nx=True, ex=self._ttl
            )
            if acquired:
                self._token = token
                return True
            # Wait before retry
            await asyncio.sleep(_RETRY_INTERVAL_SECONDS)

        logger.warning(
            "Failed to acquire lock %s within %ss", self._key, self._acquire_timeout
        )
        return False

    def release(self) -> None:
        """Release the lock if we hold it.

        Uses a Lua script to atomically check-and-delete, ensuring
        only the lock holder can release it.
        """
        if self._token is None:
            return

        # Atomic check-and-delete via Lua script
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            self._client.eval(lua_script, 1, self._key, self._token)
        except Exception as e:
            logger.warning("Failed to release lock %s: %s", self._key, e)
        finally:
            self._token = None

    async def __aenter__(self):
        acquired = await self.acquire()
        if not acquired:
            raise TimeoutError(
                f"Could not acquire lock {self._key} within {self._acquire_timeout}s"
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


class RedisLockManager:
    """Factory for creating RedisLock instances.

    Manages a Redis client connection and creates per-game locks
    with a consistent key prefix.
    """

    LOCK_KEY_PREFIX = "werewolf:lock:"

    def __init__(self, redis_client):
        self._client = redis_client

    def get_lock(
        self,
        game_id: str,
        ttl: int = _DEFAULT_LOCK_TTL_SECONDS,
        acquire_timeout: float = _DEFAULT_ACQUIRE_TIMEOUT_SECONDS,
    ) -> RedisLock:
        """Create a distributed lock for the specified game."""
        key = f"{self.LOCK_KEY_PREFIX}{game_id}"
        return RedisLock(self._client, key, ttl=ttl, acquire_timeout=acquire_timeout)
