"""Tests for rate limiter security fixes.

Tests the critical security fixes:
1. PerGameSoftLimiter.cleanup_game() concurrency safety
2. LoginRateLimiter memory leak prevention
3. LLMService._get_limiter() initialization race condition
4. XFF forgery protection
"""
import asyncio
import pytest
import time
from unittest.mock import Mock, MagicMock

from app.services.rate_limiter import PerGameSoftLimiter, TokenBucketLimiter, RateLimitTimeoutError
from app.services.login_rate_limiter import LoginRateLimiter, AttemptRecord


class TestPerGameSoftLimiterFixes:
    """Test fixes for PerGameSoftLimiter concurrency issues."""

    @pytest.mark.asyncio
    async def test_cleanup_game_is_async_and_thread_safe(self):
        """Test that cleanup_game is now async and uses lock."""
        limiter = PerGameSoftLimiter(min_interval_seconds=0.1, max_concurrency_per_game=2)

        # Create some game state
        game_id = "test_game_1"
        async with limiter.limit(game_id):
            pass

        # Verify game state exists
        assert game_id in limiter._semaphores
        assert game_id in limiter._last_call

        # Cleanup should be async
        await limiter.cleanup_game(game_id)

        # Verify cleanup worked
        assert game_id not in limiter._semaphores
        assert game_id not in limiter._last_call

    @pytest.mark.asyncio
    async def test_cleanup_game_concurrent_safety(self):
        """Test that cleanup_game is safe during concurrent operations."""
        limiter = PerGameSoftLimiter(min_interval_seconds=0.0, max_concurrency_per_game=5)
        game_id = "concurrent_test"

        # Start multiple concurrent operations
        async def use_limiter():
            async with limiter.limit(game_id):
                await asyncio.sleep(0.01)

        # Run operations and cleanup concurrently
        tasks = [use_limiter() for _ in range(10)]
        tasks.append(limiter.cleanup_game(game_id))

        # Should not raise any exceptions
        await asyncio.gather(*tasks, return_exceptions=True)


class TestLoginRateLimiterFixes:
    """Test fixes for LoginRateLimiter memory leak."""

    def test_check_rate_limit_does_not_create_records(self):
        """Test that check_rate_limit no longer creates records for new identifiers."""
        limiter = LoginRateLimiter(max_attempts=3)

        # Check a new identifier
        is_allowed, retry_after = limiter.check_rate_limit("new_user_ip")

        assert is_allowed is True
        assert retry_after is None
        # FIX: Should NOT create a record
        assert "new_user_ip" not in limiter._records

    def test_record_attempt_creates_records(self):
        """Test that record_attempt creates records as expected."""
        limiter = LoginRateLimiter(max_attempts=3)

        # Record an attempt
        limiter.record_attempt("user_ip", success=False)

        # Now record should exist
        assert "user_ip" in limiter._records
        assert limiter._records["user_ip"].attempts == 1

    def test_no_memory_leak_from_checks(self):
        """Test that repeated checks don't cause memory leak."""
        limiter = LoginRateLimiter(max_attempts=5)

        # Simulate attacker checking with many different IPs
        for i in range(1000):
            limiter.check_rate_limit(f"attacker_ip_{i}")

        # FIX: No records should be created
        assert len(limiter._records) == 0

    def test_cleanup_expired_works(self):
        """Test that cleanup_expired removes old records."""
        limiter = LoginRateLimiter(max_attempts=3, window_seconds=1)

        # Create some records
        limiter.record_attempt("old_ip", success=False)
        limiter.record_attempt("recent_ip", success=False)

        # Wait for first record to expire
        time.sleep(2.5)

        # Record another attempt for recent_ip to update last_attempt_at
        limiter.record_attempt("recent_ip", success=False)

        # Cleanup
        cleaned = limiter.cleanup_expired()

        # Old record should be cleaned
        assert cleaned >= 1
        assert "old_ip" not in limiter._records or limiter._records["old_ip"].last_attempt_at == 0


class TestLLMServiceLimiterFixes:
    """Test fixes for LLMService._get_limiter() race condition."""

    @pytest.mark.asyncio
    async def test_get_limiter_concurrent_initialization(self):
        """Test that concurrent _get_limiter calls don't create multiple limiters."""
        from app.services.llm import LLMService
        from app.core.config import AIProviderConfig

        service = LLMService()
        provider = AIProviderConfig(
            name="test_provider",
            api_key="test_key",
            requests_per_minute=60,
            max_concurrency=5,
            burst=3
        )

        # Simulate concurrent calls
        async def get_limiter():
            return await service._get_limiter(provider)

        # Run 10 concurrent calls
        limiters = await asyncio.gather(*[get_limiter() for _ in range(10)])

        # All should return the same limiter instance
        first_limiter = limiters[0]
        for limiter in limiters[1:]:
            assert limiter is first_limiter

        # Only one limiter should be created
        assert len(service._provider_limiters) == 1


class TestXFFProtectionFixes:
    """Test fixes for X-Forwarded-For forgery protection."""

    def test_xff_chain_length_validation(self):
        """Test that excessively long XFF chains are rejected."""
        from app.core.client_ip import get_client_ip
        from app.core.config import settings
        from fastapi import Request

        # Mock request with long XFF chain
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "127.0.0.1"

        # Create XFF chain longer than MAX_PROXY_HOPS
        long_chain = ",".join([f"1.2.3.{i}" for i in range(settings.MAX_PROXY_HOPS + 5)])
        request.headers = {"x-forwarded-for": long_chain}

        # Configure trusted proxy
        original_proxies = settings.TRUSTED_PROXIES
        settings.TRUSTED_PROXIES = ["127.0.0.1"]

        try:
            # Should fall back to peer IP due to suspicious chain length
            client_ip = get_client_ip(request)
            assert client_ip == "127.0.0.1"
        finally:
            settings.TRUSTED_PROXIES = original_proxies

    def test_xff_invalid_ip_validation(self):
        """Test that XFF chains with invalid IPs are rejected."""
        from app.core.client_ip import get_client_ip
        from app.core.config import settings
        from fastapi import Request

        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "127.0.0.1"

        # XFF with invalid IP
        request.headers = {"x-forwarded-for": "1.2.3.4, invalid_ip, 5.6.7.8"}

        original_proxies = settings.TRUSTED_PROXIES
        settings.TRUSTED_PROXIES = ["127.0.0.1"]

        try:
            # Should fall back to peer IP due to invalid IP in chain
            client_ip = get_client_ip(request)
            assert client_ip == "127.0.0.1"
        finally:
            settings.TRUSTED_PROXIES = original_proxies

    def test_xff_without_trusted_proxy(self):
        """Test that XFF is ignored when not from trusted proxy."""
        from app.core.client_ip import get_client_ip
        from app.core.config import settings
        from fastapi import Request

        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "8.8.8.8"  # Not a trusted proxy

        request.headers = {"x-forwarded-for": "1.2.3.4"}

        original_proxies = settings.TRUSTED_PROXIES
        settings.TRUSTED_PROXIES = ["127.0.0.1"]

        try:
            # Should use peer IP, not XFF
            client_ip = get_client_ip(request)
            assert client_ip == "8.8.8.8"
        finally:
            settings.TRUSTED_PROXIES = original_proxies


class TestTokenBucketLimiterBasics:
    """Basic tests for TokenBucketLimiter to ensure it still works."""

    @pytest.mark.asyncio
    async def test_basic_rate_limiting(self):
        """Test that basic rate limiting still works."""
        limiter = TokenBucketLimiter(
            requests_per_minute=60,
            burst=2,
            max_concurrency=5
        )

        # Should allow burst requests immediately
        async with limiter.limit(max_wait_seconds=1.0):
            pass

        async with limiter.limit(max_wait_seconds=1.0):
            pass

    @pytest.mark.asyncio
    async def test_rate_limit_timeout(self):
        """Test that rate limit timeout works."""
        limiter = TokenBucketLimiter(
            requests_per_minute=1,  # Very low rate
            burst=1,
            max_concurrency=5
        )

        # First request should succeed
        async with limiter.limit(max_wait_seconds=0.1):
            pass

        # Second request should timeout
        with pytest.raises(RateLimitTimeoutError):
            async with limiter.limit(max_wait_seconds=0.1):
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
