"""Login rate limiter for brute-force protection.

This module provides rate limiting for login attempts to prevent
brute-force attacks on authentication endpoints.
"""
import time
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class AttemptRecord:
    """Record of login attempts for an identifier."""
    attempts: int = 0
    first_attempt_at: float = 0.0
    locked_until: float = 0.0
    last_attempt_at: float = 0.0


class LoginRateLimiter:
    """In-memory rate limiter for login attempts.

    Uses sliding window approach with progressive lockout.

    Configuration:
        max_attempts: Maximum attempts before lockout (default: 5)
        window_seconds: Time window for counting attempts (default: 300 = 5 min)
        lockout_seconds: Base lockout duration (default: 300 = 5 min)
        max_lockout_seconds: Maximum lockout duration (default: 3600 = 1 hour)

    Progressive lockout:
        - 1st lockout: 5 minutes
        - 2nd lockout: 10 minutes
        - 3rd lockout: 20 minutes
        - ... up to max_lockout_seconds
    """

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 300,
        lockout_seconds: int = 300,
        max_lockout_seconds: int = 3600,
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self.max_lockout_seconds = max_lockout_seconds

        # FIX: Use regular dict instead of defaultdict to prevent memory leak
        # Only create records when actually recording attempts, not on checks
        self._records: Dict[str, AttemptRecord] = {}
        self._lockout_counts: Dict[str, int] = {}
        self._lock = Lock()

    def check_rate_limit(self, identifier: str) -> Tuple[bool, Optional[int]]:
        """Check if identifier is rate limited.

        FIX: No longer creates records on check - only reads existing ones.
        This prevents memory leak from attackers checking with random identifiers.

        Args:
            identifier: IP address or username to check

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
            - is_allowed: True if attempt is allowed
            - retry_after_seconds: Seconds until retry allowed (if blocked)
        """
        now = time.time()

        with self._lock:
            # FIX: Don't create record if it doesn't exist
            if identifier not in self._records:
                return True, None  # New identifier, allow

            record = self._records[identifier]

            # Check if currently locked out
            if record.locked_until > now:
                retry_after = int(record.locked_until - now)
                logger.warning(
                    f"Login attempt blocked for {identifier}: locked for {retry_after}s"
                )
                return False, retry_after

            # Check if window has expired - reset if so
            if record.first_attempt_at > 0:
                window_end = record.first_attempt_at + self.window_seconds
                if now > window_end:
                    # Window expired, reset attempts
                    record.attempts = 0
                    record.first_attempt_at = 0.0

            return True, None

    def record_attempt(self, identifier: str, success: bool) -> None:
        """Record a login attempt.

        Args:
            identifier: IP address or username
            success: Whether the login was successful
        """
        now = time.time()

        with self._lock:
            # FIX: Create record only when recording attempts
            if identifier not in self._records:
                self._records[identifier] = AttemptRecord()

            record = self._records[identifier]

            if success:
                # Successful login - reset attempts but keep lockout count
                record.attempts = 0
                record.first_attempt_at = 0.0
                record.locked_until = 0.0
                logger.info(f"Successful login for {identifier}, attempts reset")
                return

            # Failed attempt
            if record.first_attempt_at == 0:
                record.first_attempt_at = now

            record.attempts += 1
            record.last_attempt_at = now

            logger.info(
                f"Failed login attempt for {identifier}: "
                f"{record.attempts}/{self.max_attempts}"
            )

            # Check if should lock out
            if record.attempts >= self.max_attempts:
                # FIX: Initialize lockout count if not exists
                if identifier not in self._lockout_counts:
                    self._lockout_counts[identifier] = 0

                self._lockout_counts[identifier] += 1
                lockout_multiplier = min(
                    self._lockout_counts[identifier],
                    self.max_lockout_seconds // self.lockout_seconds
                )
                lockout_duration = min(
                    self.lockout_seconds * lockout_multiplier,
                    self.max_lockout_seconds
                )
                record.locked_until = now + lockout_duration
                record.attempts = 0
                record.first_attempt_at = 0.0

                logger.warning(
                    f"Account {identifier} locked out for {lockout_duration}s "
                    f"(lockout #{self._lockout_counts[identifier]})"
                )

    def reset(self, identifier: str) -> None:
        """Reset all rate limiting for an identifier.

        Use this when an admin manually unlocks an account.
        """
        with self._lock:
            if identifier in self._records:
                del self._records[identifier]
            if identifier in self._lockout_counts:
                del self._lockout_counts[identifier]
            logger.info(f"Rate limit reset for {identifier}")

    def cleanup_expired(self) -> int:
        """Clean up expired records to free memory.

        Returns:
            Number of records cleaned up
        """
        now = time.time()
        cleanup_threshold = now - (self.window_seconds * 2)  # 2x window
        cleaned = 0

        with self._lock:
            expired_keys = [
                k for k, v in self._records.items()
                if v.last_attempt_at < cleanup_threshold and v.locked_until < now
            ]
            for key in expired_keys:
                del self._records[key]
                if key in self._lockout_counts:
                    del self._lockout_counts[key]
                cleaned += 1

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired rate limit records")

        return cleaned


# Global instance for admin login
admin_login_limiter = LoginRateLimiter(
    max_attempts=5,
    window_seconds=300,      # 5 minutes
    lockout_seconds=300,     # 5 minutes base lockout
    max_lockout_seconds=3600 # 1 hour max lockout
)

# Instance for regular user login (more lenient)
user_login_limiter = LoginRateLimiter(
    max_attempts=10,
    window_seconds=600,      # 10 minutes
    lockout_seconds=60,      # 1 minute base lockout
    max_lockout_seconds=900  # 15 minutes max lockout
)
