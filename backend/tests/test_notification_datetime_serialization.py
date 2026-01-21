"""Tests for notification datetime serialization with UTC 'Z' suffix."""
import unittest
from datetime import datetime, timedelta, timezone

from app.schemas.notification import NotificationCategory, NotificationPublic


class TestNotificationDatetimeSerialization(unittest.TestCase):
    """Test cases for datetime serialization in notification schemas."""

    def test_naive_datetime_serializes_with_z_suffix(self) -> None:
        """Naive datetime should be treated as UTC and serialized with 'Z' suffix."""
        notification = NotificationPublic(
            id="n1",
            user_id="u1",
            category=NotificationCategory.SYSTEM,
            title="Test notification",
            body="Test body",
            data={},
            created_at=datetime(2025, 1, 21, 12, 0, 0),
            read_at=None,
        )

        dumped = notification.model_dump(mode="json")
        self.assertEqual(dumped["created_at"], "2025-01-21T12:00:00Z")
        self.assertIsNone(dumped["read_at"])

    def test_aware_datetime_converts_to_utc_and_uses_z_suffix(self) -> None:
        """Aware datetime should be converted to UTC and serialized with 'Z' suffix."""
        tz_plus_8 = timezone(timedelta(hours=8))
        # 2025-01-21T20:00:00+08:00 == 2025-01-21T12:00:00Z
        created_at_local = datetime(2025, 1, 21, 20, 0, 0, tzinfo=tz_plus_8)

        notification = NotificationPublic(
            id="n1",
            user_id="u1",
            category=NotificationCategory.SYSTEM,
            title="Test notification",
            body="Test body",
            data={},
            created_at=created_at_local,
            read_at=datetime(2025, 1, 21, 20, 1, 0, tzinfo=tz_plus_8),  # 12:01Z
        )

        dumped = notification.model_dump(mode="json")
        self.assertEqual(dumped["created_at"], "2025-01-21T12:00:00Z")
        self.assertEqual(dumped["read_at"], "2025-01-21T12:01:00Z")

    def test_utc_aware_datetime_uses_z_suffix(self) -> None:
        """UTC aware datetime should be serialized with 'Z' suffix (not +00:00)."""
        notification = NotificationPublic(
            id="n1",
            user_id="u1",
            category=NotificationCategory.GAME,
            title="Game notification",
            body="Game started",
            data={"game_id": "g1"},
            created_at=datetime(2025, 1, 21, 12, 0, 0, tzinfo=timezone.utc),
            read_at=None,
        )

        dumped = notification.model_dump(mode="json")
        self.assertEqual(dumped["created_at"], "2025-01-21T12:00:00Z")


if __name__ == "__main__":
    unittest.main(verbosity=2)
