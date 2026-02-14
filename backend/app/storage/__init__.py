"""Game state storage abstraction layer.

Provides a pluggable backend interface for game state persistence,
enabling migration from in-memory storage to Redis or other backends.

Configuration:
    GAME_STORE_BACKEND=memory (default) | redis
    REDIS_URL=redis://localhost:6379/0 (required when backend=redis)
"""

import logging
import os

from app.storage.backend import GameStoreBackend
from app.storage.memory import InMemoryBackend

logger = logging.getLogger(__name__)

__all__ = ["GameStoreBackend", "InMemoryBackend", "create_backend"]


def create_backend() -> GameStoreBackend:
    """Create a storage backend based on environment configuration.

    Reads GAME_STORE_BACKEND env var:
    - "memory" (default): In-memory dict storage
    - "redis": Redis-backed storage (requires REDIS_URL)

    Returns:
        Configured GameStoreBackend instance
    """
    backend_type = os.getenv("GAME_STORE_BACKEND", "memory").lower().strip()

    if backend_type == "redis":
        redis_url = os.getenv("REDIS_URL", "").strip()
        if not redis_url:
            logger.warning(
                "GAME_STORE_BACKEND=redis but REDIS_URL not set, falling back to memory"
            )
            return InMemoryBackend()
        try:
            from app.storage.redis_backend import RedisBackend
            rb = RedisBackend(redis_url)
            if rb.ping():
                logger.info("Game store backend: Redis (%s)", redis_url.split("@")[-1])
                return rb
            else:
                logger.warning("Redis ping failed, falling back to memory backend")
                return InMemoryBackend()
        except Exception as e:
            logger.warning("Failed to initialize Redis backend: %s, falling back to memory", e)
            return InMemoryBackend()

    if backend_type != "memory":
        logger.warning("Unknown GAME_STORE_BACKEND=%s, using memory", backend_type)

    return InMemoryBackend()
