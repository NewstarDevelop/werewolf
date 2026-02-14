"""Rate limiter for game API endpoints.

Prevents abuse of game step/action endpoints that trigger LLM calls.
Uses per-player sliding window to limit request frequency.
"""
import time
import logging
from typing import Dict, Optional, Tuple
from threading import Lock

logger = logging.getLogger(__name__)


class GameApiRateLimiter:
    """Per-player rate limiter for game API calls (step/action).

    Limits how frequently a single player can call game endpoints
    to prevent LLM quota abuse and per-game lock contention.

    Configuration:
        max_requests: Maximum requests per window (default: 30)
        window_seconds: Sliding window duration (default: 60s)
    """

    def __init__(
        self,
        max_requests: int = 30,
        window_seconds: int = 60,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: Dict[str, list[float]] = {}
        self._lock = Lock()

    def check_rate_limit(self, player_id: str) -> Tuple[bool, Optional[int]]:
        """Check if a player is rate limited.

        Args:
            player_id: Player identifier from JWT token

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            if player_id not in self._timestamps:
                return True, None

            # Remove expired timestamps
            timestamps = self._timestamps[player_id]
            self._timestamps[player_id] = [t for t in timestamps if t > cutoff]
            timestamps = self._timestamps[player_id]

            if len(timestamps) >= self.max_requests:
                # Find when the oldest relevant timestamp will expire
                retry_after = int(timestamps[0] - cutoff) + 1
                return False, max(retry_after, 1)

            return True, None

    def record_request(self, player_id: str) -> None:
        """Record a game API request."""
        now = time.time()
        with self._lock:
            if player_id not in self._timestamps:
                self._timestamps[player_id] = []
            self._timestamps[player_id].append(now)

    def cleanup_expired(self) -> int:
        """Clean up expired records to free memory."""
        now = time.time()
        cutoff = now - self.window_seconds * 2
        cleaned = 0

        with self._lock:
            expired_keys = [
                k for k, v in self._timestamps.items()
                if not v or max(v) < cutoff
            ]
            for key in expired_keys:
                del self._timestamps[key]
                cleaned += 1

        if cleaned > 0:
            logger.debug(f"Cleaned up {cleaned} expired game rate limit records")
        return cleaned


# Global instance for game step/action endpoints
# 30 requests per 60 seconds per player
game_api_limiter = GameApiRateLimiter(
    max_requests=30,
    window_seconds=60,
)
