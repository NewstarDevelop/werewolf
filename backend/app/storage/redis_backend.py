"""Redis storage backend for game state.

Stores serialized Game objects in Redis, enabling multi-instance
deployment with shared game state.

Requires:
- redis>=5.0 (already in requirements.txt)
- REDIS_URL environment variable (e.g. redis://localhost:6379/0)
"""

import json
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.game import Game

logger = logging.getLogger(__name__)

# Key prefix for game state in Redis
_KEY_PREFIX = "werewolf:game:"


def _game_key(game_id: str) -> str:
    """Build the Redis key for a game."""
    return f"{_KEY_PREFIX}{game_id}"


class RedisBackend:
    """Redis-backed game storage.

    Stores Game objects as JSON blobs in Redis. Each get() returns a freshly
    deserialized copy, so callers must use GameStore.save_game_state() to
    persist mutations back to Redis (handled by GameStore's write-back cache).

    Key schema:
        werewolf:game:{game_id} -> JSON blob of serialized Game

    TTL is managed by GameStore (not Redis EXPIRE), to keep behavior
    consistent with InMemoryBackend. A future optimization could use
    Redis EXPIRE as a safety net.
    """

    def __init__(self, redis_url: str, key_prefix: str = _KEY_PREFIX):
        import redis as redis_lib
        self._client = redis_lib.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        self._key_prefix = key_prefix

    def _key(self, game_id: str) -> str:
        return f"{self._key_prefix}{game_id}"

    def get(self, game_id: str) -> Optional["Game"]:
        try:
            data = self._client.get(self._key(game_id))
            if data is None:
                return None
            from app.services.game_persistence import _deserialize_game
            return _deserialize_game(json.loads(data))
        except Exception as e:
            logger.error(f"Redis GET failed for game {game_id}: {e}")
            return None

    def put(self, game_id: str, game: "Game") -> None:
        try:
            from app.services.game_persistence import _serialize_game
            data = json.dumps(_serialize_game(game), ensure_ascii=False)
            self._client.set(self._key(game_id), data)
        except Exception as e:
            logger.error(f"Redis SET failed for game {game_id}: {e}")

    def delete(self, game_id: str) -> bool:
        try:
            return self._client.delete(self._key(game_id)) > 0
        except Exception as e:
            logger.error(f"Redis DELETE failed for game {game_id}: {e}")
            return False

    def exists(self, game_id: str) -> bool:
        try:
            return bool(self._client.exists(self._key(game_id)))
        except Exception as e:
            logger.error(f"Redis EXISTS failed for game {game_id}: {e}")
            return False

    def count(self) -> int:
        try:
            keys = self._client.keys(f"{self._key_prefix}*")
            return len(keys)
        except Exception as e:
            logger.error(f"Redis COUNT failed: {e}")
            return 0

    def all_ids(self) -> list[str]:
        try:
            keys = self._client.keys(f"{self._key_prefix}*")
            prefix_len = len(self._key_prefix)
            return [k[prefix_len:] for k in keys]
        except Exception as e:
            logger.error(f"Redis ALL_IDS failed: {e}")
            return []

    def ping(self) -> bool:
        """Health check — verify Redis connectivity."""
        try:
            return self._client.ping()
        except Exception:
            return False
