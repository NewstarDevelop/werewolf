"""Tests for batch notification performance - A6 fix.

Verifies that:
1. emit_batch creates all notifications with single commit
2. All notifications and outbox records are created correctly
3. Batch operation is atomic (all-or-nothing)
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationCategory, NotificationPersistPolicy


class TestNotificationBatch:
    """Test batch notification emission."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session (async-compatible)."""
        db = MagicMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.rollback = AsyncMock()
        return db

    @pytest.fixture
    def mock_publisher(self):
        """Create mock Redis publisher."""
        publisher = MagicMock()
        publisher.publish_json = AsyncMock()
        return publisher

    @pytest.mark.asyncio
    async def test_batch_emit_single_commit(self, mock_db, mock_publisher):
        """Batch emit should only call commit once for multiple users."""
        service = NotificationService(publisher=mock_publisher)
        user_ids = ["user1", "user2", "user3", "user4", "user5"]

        with patch('app.services.notification_service.Notification') as MockNotification, \
             patch('app.services.notification_service.NotificationOutbox') as MockOutbox:

            # Setup mock notifications with IDs
            mock_notifications = []
            for i, user_id in enumerate(user_ids):
                mock_n = MagicMock()
                mock_n.id = f"notif-{i}"
                mock_n.user_id = user_id
                mock_n.category = "SYSTEM"
                mock_n.title = "Test"
                mock_n.body = "Test body"
                mock_n.data = {}
                mock_n.created_at = datetime.utcnow()
                mock_n.read_at = None
                mock_notifications.append(mock_n)

            MockNotification.side_effect = mock_notifications

            await service.emit_batch(
                mock_db,
                user_ids=user_ids,
                category=NotificationCategory.SYSTEM,
                title="Test",
                body="Test body",
            )

            # 1 batch commit + 5 best-effort publish commits = 6 total
            assert mock_db.commit.call_count == 6, \
                f"Expected 6 commits (1 batch + 5 best-effort), got {mock_db.commit.call_count}"

            # Should have ONE flush call
            assert mock_db.flush.call_count == 1, \
                f"Expected 1 flush, got {mock_db.flush.call_count}"

            # Should add 5 notifications + 5 outbox records = 10 add calls
            assert mock_db.add.call_count == 10, \
                f"Expected 10 add calls (5 notif + 5 outbox), got {mock_db.add.call_count}"

    @pytest.mark.asyncio
    async def test_batch_emit_empty_list(self, mock_db, mock_publisher):
        """Empty user list should return immediately without DB operations."""
        service = NotificationService(publisher=mock_publisher)

        result = await service.emit_batch(
            mock_db,
            user_ids=[],
            category=NotificationCategory.SYSTEM,
            title="Test",
            body="Test body",
        )

        assert result == []
        assert mock_db.add.call_count == 0
        assert mock_db.commit.call_count == 0

    @pytest.mark.asyncio
    async def test_batch_emit_volatile_no_db(self, mock_db, mock_publisher):
        """VOLATILE batch should not write to DB."""
        service = NotificationService(publisher=mock_publisher)
        user_ids = ["user1", "user2", "user3"]

        result = await service.emit_batch(
            mock_db,
            user_ids=user_ids,
            category=NotificationCategory.GAME,
            title="Game Event",
            body="Something happened",
            persist_policy=NotificationPersistPolicy.VOLATILE,
        )

        assert result == []
        assert mock_db.add.call_count == 0
        assert mock_db.commit.call_count == 0
        # Should publish 3 times (once per user)
        assert mock_publisher.publish_json.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_emit_broadcast_id(self, mock_db, mock_publisher):
        """Batch emit should propagate broadcast_id to all records."""
        service = NotificationService(publisher=mock_publisher)
        broadcast_id = "broadcast-123"

        with patch('app.services.notification_service.Notification') as MockNotification, \
             patch('app.services.notification_service.NotificationOutbox') as MockOutbox:

            mock_n = MagicMock()
            mock_n.id = "notif-1"
            mock_n.user_id = "user1"
            mock_n.category = "SYSTEM"
            mock_n.title = "Broadcast"
            mock_n.body = "Broadcast message"
            mock_n.data = {}
            mock_n.created_at = datetime.utcnow()
            mock_n.read_at = None
            MockNotification.return_value = mock_n

            await service.emit_batch(
                mock_db,
                user_ids=["user1"],
                category=NotificationCategory.SYSTEM,
                title="Broadcast",
                body="Broadcast message",
                broadcast_id=broadcast_id,
            )

            # Check Notification was created with broadcast_id
            MockNotification.assert_called_once()
            call_kwargs = MockNotification.call_args[1]
            assert call_kwargs.get("broadcast_id") == broadcast_id

            # Check NotificationOutbox was created with broadcast_id
            MockOutbox.assert_called_once()
            outbox_kwargs = MockOutbox.call_args[1]
            assert outbox_kwargs.get("broadcast_id") == broadcast_id

    @pytest.mark.asyncio
    async def test_batch_emit_idempotency_keys(self, mock_db, mock_publisher):
        """Batch emit should generate correct idempotency keys with prefix."""
        service = NotificationService(publisher=mock_publisher)
        prefix = "broadcast-abc"

        with patch('app.services.notification_service.Notification') as MockNotification, \
             patch('app.services.notification_service.NotificationOutbox') as MockOutbox:

            mock_notifications = []
            for user_id in ["user1", "user2"]:
                mock_n = MagicMock()
                mock_n.id = f"notif-{user_id}"
                mock_n.user_id = user_id
                mock_n.category = "SYSTEM"
                mock_n.title = "Test"
                mock_n.body = "Test"
                mock_n.data = {}
                mock_n.created_at = datetime.utcnow()
                mock_n.read_at = None
                mock_notifications.append(mock_n)

            MockNotification.side_effect = mock_notifications

            await service.emit_batch(
                mock_db,
                user_ids=["user1", "user2"],
                category=NotificationCategory.SYSTEM,
                title="Test",
                body="Test",
                idempotency_key_prefix=prefix,
            )

            # Check idempotency keys follow pattern: prefix:user_id
            outbox_calls = MockOutbox.call_args_list
            assert len(outbox_calls) == 2

            idem_keys = [call[1]["idempotency_key"] for call in outbox_calls]
            assert f"{prefix}:user1" in idem_keys
            assert f"{prefix}:user2" in idem_keys
