"""Async rate limiting utilities for multi-room concurrent LLM calls.

This module provides two types of rate limiters:
1. TokenBucketLimiter: Provider-level hard rate limiting with concurrency control
2. PerGameSoftLimiter: Per-game soft limiting for fairness across concurrent games

Usage:
    # Provider-level limiting
    limiter = TokenBucketLimiter(requests_per_minute=60, burst=1, max_concurrency=5)
    async with limiter.limit(max_wait_seconds=5.0):
        await make_api_call()

    # Per-game soft limiting
    game_limiter = PerGameSoftLimiter(min_interval_seconds=0.5, max_concurrency_per_game=1)
    async with game_limiter.limit(game_id, max_wait_seconds=3.0):
        await make_api_call()
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimitTimeoutError(Exception):
    """Raised when waiting for rate/concurrency budget exceeds max_wait_seconds."""
    pass


class TokenBucketLimiter:
    """Provider-scoped token bucket rate limiter with concurrency control.

    This limiter combines:
    - Token bucket algorithm for rate limiting (RPM/RPS)
    - Semaphore for concurrent request limiting
    - Async lock for thread-safe token operations

    Attributes:
        requests_per_minute: Maximum requests allowed per minute
        burst: Token bucket capacity (allows short bursts)
        max_concurrency: Maximum concurrent in-flight requests
    """

    def __init__(
        self,
        *,
        requests_per_minute: int = 60,
        burst: int = 1,
        max_concurrency: int = 5,
    ):
        rpm = max(1, int(requests_per_minute))
        self._rate_per_sec = rpm / 60.0
        self._capacity = max(1, int(burst))
        self._tokens = float(self._capacity)
        self._last_refill: Optional[float] = None

        self._token_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max(1, int(max_concurrency)))

        self._provider_name: str = ""  # Set externally for logging

    def _refill(self, now: float) -> None:
        """Refill tokens based on elapsed time."""
        if self._last_refill is None:
            self._last_refill = now
            return

        elapsed = now - self._last_refill
        if elapsed <= 0:
            return

        self._tokens = min(self._capacity, self._tokens + (elapsed * self._rate_per_sec))
        self._last_refill = now

    async def _acquire_token(self, *, deadline: Optional[float], amount: float = 1.0) -> None:
        """Acquire a token from the bucket, waiting if necessary."""
        while True:
            async with self._token_lock:
                now = time.monotonic()
                self._refill(now)

                if self._tokens >= amount:
                    self._tokens -= amount
                    return

                # Calculate wait time for next token
                if self._rate_per_sec <= 0:
                    wait_seconds = float("inf")
                else:
                    missing = amount - self._tokens
                    wait_seconds = missing / self._rate_per_sec

            # Check deadline before waiting
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RateLimitTimeoutError(
                        f"Timed out waiting for rate-limit token (provider={self._provider_name})"
                    )
                wait_seconds = min(wait_seconds, remaining)

            logger.debug(f"Rate limiter waiting {wait_seconds:.2f}s for token")
            await asyncio.sleep(wait_seconds)

    async def _refund_token(self, amount: float = 1.0) -> None:
        """Refund a token back to the bucket (used on timeout)."""
        async with self._token_lock:
            self._tokens = min(self._capacity, self._tokens + amount)

    async def _acquire_concurrency(self, *, deadline: Optional[float]) -> None:
        """Acquire a concurrency slot from the semaphore."""
        if deadline is None:
            await self._semaphore.acquire()
            return

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RateLimitTimeoutError(
                f"Timed out waiting for concurrency slot (provider={self._provider_name})"
            )

        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=remaining)
        except asyncio.TimeoutError as e:
            raise RateLimitTimeoutError(
                f"Timed out waiting for concurrency slot (provider={self._provider_name})"
            ) from e

    @asynccontextmanager
    async def limit(self, *, max_wait_seconds: Optional[float] = None):
        """Context manager for rate-limited API calls.

        Args:
            max_wait_seconds: Maximum time to wait for rate limit. None means wait forever.

        Raises:
            RateLimitTimeoutError: If waiting exceeds max_wait_seconds

        Usage:
            async with limiter.limit(max_wait_seconds=5.0):
                await make_api_call()
        """
        deadline = None if max_wait_seconds is None else (time.monotonic() + float(max_wait_seconds))

        # First acquire token (rate limiting)
        await self._acquire_token(deadline=deadline, amount=1.0)

        # Then acquire concurrency slot
        try:
            await self._acquire_concurrency(deadline=deadline)
        except (RateLimitTimeoutError, asyncio.CancelledError):
            # Refund token if we couldn't get concurrency slot
            await self._refund_token(1.0)
            raise

        try:
            yield
        finally:
            self._semaphore.release()


class PerGameSoftLimiter:
    """Soft per-game limiter to improve fairness across concurrent games.

    This limiter ensures that one game doesn't monopolize the API quota,
    allowing multiple games to progress fairly.

    Attributes:
        min_interval_seconds: Minimum time between calls for the same game
        max_concurrency_per_game: Maximum concurrent calls per game
    """

    def __init__(
        self,
        *,
        min_interval_seconds: float = 0.0,
        max_concurrency_per_game: int = 1,
    ):
        self._min_interval_seconds = max(0.0, float(min_interval_seconds))
        self._max_concurrency_per_game = max(1, int(max_concurrency_per_game))

        self._global_lock = asyncio.Lock()
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._last_call: dict[str, float] = {}

    async def _get_semaphore(self, game_id: str) -> asyncio.Semaphore:
        """Get or create semaphore for a game."""
        async with self._global_lock:
            sem = self._semaphores.get(game_id)
            if sem is None:
                sem = asyncio.Semaphore(self._max_concurrency_per_game)
                self._semaphores[game_id] = sem
            return sem

    async def _maybe_wait_interval(self, game_id: str, *, deadline: Optional[float]) -> None:
        """Wait for minimum interval if needed."""
        if self._min_interval_seconds <= 0:
            return

        async with self._global_lock:
            last = self._last_call.get(game_id)

        if last is None:
            return

        wait_seconds = (last + self._min_interval_seconds) - time.monotonic()
        if wait_seconds <= 0:
            return

        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RateLimitTimeoutError(
                    f"Timed out waiting for per-game interval (game={game_id})"
                )
            wait_seconds = min(wait_seconds, remaining)

        logger.debug(f"Per-game limiter waiting {wait_seconds:.2f}s for game {game_id}")
        await asyncio.sleep(wait_seconds)

    async def _touch(self, game_id: str) -> None:
        """Update last call time for a game."""
        async with self._global_lock:
            self._last_call[game_id] = time.monotonic()

    def cleanup_game(self, game_id: str) -> None:
        """Clean up resources for a finished game.

        Call this when a game ends to prevent memory leaks.
        """
        # Note: This is synchronous and should be called from a sync context
        # or wrapped in asyncio.create_task if called from async
        if game_id in self._semaphores:
            del self._semaphores[game_id]
        if game_id in self._last_call:
            del self._last_call[game_id]

    @asynccontextmanager
    async def limit(self, game_id: str, *, max_wait_seconds: Optional[float] = None):
        """Context manager for per-game rate limiting.

        Args:
            game_id: The game identifier
            max_wait_seconds: Maximum time to wait. None means wait forever.

        Raises:
            RateLimitTimeoutError: If waiting exceeds max_wait_seconds
        """
        deadline = None if max_wait_seconds is None else (time.monotonic() + float(max_wait_seconds))

        semaphore = await self._get_semaphore(game_id)

        # Acquire semaphore with timeout
        if deadline is None:
            await semaphore.acquire()
        else:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RateLimitTimeoutError(
                    f"Timed out waiting for per-game slot (game={game_id})"
                )
            try:
                await asyncio.wait_for(semaphore.acquire(), timeout=remaining)
            except asyncio.TimeoutError as e:
                raise RateLimitTimeoutError(
                    f"Timed out waiting for per-game slot (game={game_id})"
                ) from e

        try:
            await self._maybe_wait_interval(game_id, deadline=deadline)
            await self._touch(game_id)
            yield
        finally:
            semaphore.release()
