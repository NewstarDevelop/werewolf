"""
NotificationService.

Responsibilities:
- Apply tiered storage policy:
  - VOLATILE: publish only (no DB write)
  - DURABLE: write Notification + NotificationOutbox and (best-effort) publish
- Keep WebSocket envelope consistent with existing system:
  { "type": "<message_type>", "data": { ... } }

Outbox note:
- This module creates outbox rows. A separate worker is expected to publish PENDING
  outbox rows and mark them SENT/FAILED with retries.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationOutbox
from app.schemas.notification import NotificationCategory, NotificationPersistPolicy, NotificationPublic
from app.services.redis_pubsub import RedisPublisher

logger = logging.getLogger(__name__)


class NotificationService:
    """Core notification logic shared by REST/WS/business events."""

    DEFAULT_TOPIC = "notifications"

    def __init__(self, publisher: Optional[RedisPublisher] = None) -> None:
        self._publisher = publisher

    def _to_public(self, n: Notification) -> NotificationPublic:
        """Serialize ORM model into Pydantic schema (REST + WS reuse)."""
        return NotificationPublic(
            id=n.id,
            user_id=n.user_id,
            category=NotificationCategory(n.category),
            title=n.title,
            body=n.body,
            data=dict(n.data or {}),
            created_at=n.created_at,
            read_at=n.read_at,
        )

    def _build_ws_message(self, *, persisted: bool, notification: Optional[NotificationPublic]) -> dict[str, Any]:
        """
        Build WS envelope pieces.

        Redis Pub/Sub message uses:
        - user_id for routing
        - message_type + data for WS forwarding
        """
        if persisted:
            return {
                "persisted": True,
                "notification": notification.model_dump(mode="json"),
            }

        return {
            "persisted": False,
            "event_id": str(uuid.uuid4()),
            "notification": notification.model_dump(mode="json") if notification else None,
        }

    async def emit(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        category: NotificationCategory,
        title: str,
        body: str,
        data: Optional[dict[str, Any]] = None,
        persist_policy: NotificationPersistPolicy = NotificationPersistPolicy.DURABLE,
        topic: str = DEFAULT_TOPIC,
        idempotency_key: Optional[str] = None,
        broadcast_id: Optional[str] = None,
    ) -> Optional[NotificationPublic]:
        """
        Emit a notification under tiered storage policy.

        Returns:
        - NotificationPublic for DURABLE
        - None for VOLATILE (no DB id to return, unless you decide to create synthetic IDs)
        """
        payload_data = data or {}

        if persist_policy == NotificationPersistPolicy.VOLATILE:
            await self._publish_volatile(
                user_id=user_id,
                category=category,
                title=title,
                body=body,
                data=payload_data,
                topic=topic,
            )
            return None

        # DURABLE path: write Notification + Outbox in DB first (source of truth).
        notification = Notification(
            user_id=user_id,
            category=category.value,
            title=title,
            body=body,
            data=payload_data,
            broadcast_id=broadcast_id,
        )
        db.add(notification)
        await db.flush()  # ensure notification.id is available

        public = self._to_public(notification)

        # Outbox is self-contained so workers can publish without DB joins.
        outbox_payload = {
            "version": 1,
            "user_id": user_id,
            "message_type": "notification",
            "data": self._build_ws_message(persisted=True, notification=public),
        }

        outbox = NotificationOutbox(
            idempotency_key=idempotency_key or notification.id,
            user_id=user_id,
            topic=topic,
            payload=outbox_payload,
            status="PENDING",
            attempts=0,
            available_at=datetime.now(timezone.utc),
            broadcast_id=broadcast_id,
        )
        db.add(outbox)
        await db.commit()
        await db.refresh(notification)

        # Best-effort publish now. If this fails, outbox remains PENDING for worker retry.
        await self._best_effort_publish_and_mark_sent(db=db, outbox=outbox)

        return public

    async def _publish_volatile(
        self,
        *,
        user_id: str,
        category: NotificationCategory,
        title: str,
        body: str,
        data: dict[str, Any],
        topic: str,
    ) -> None:
        """
        Publish a volatile notification (no DB write).

        This is intended for high-frequency game events where persistence is not desired.
        """
        if not self._publisher:
            return

        # For volatile, we still include a "notification-like" object for UI rendering consistency,
        # but it does not have a durable DB id.
        temp_notification = NotificationPublic(
            id=str(uuid.uuid4()),
            user_id=user_id,
            category=category,
            title=title,
            body=body,
            data=data,
            created_at=datetime.now(timezone.utc),
            read_at=None,
        )

        payload = {
            "version": 1,
            "user_id": user_id,
            "message_type": "notification",
            "data": self._build_ws_message(persisted=False, notification=temp_notification),
        }

        try:
            await self._publisher.publish_json(topic, payload)
        except Exception as e:
            logger.warning(f"[notifications] volatile publish failed: {e}")

    async def _best_effort_publish_and_mark_sent(self, *, db: AsyncSession, outbox: NotificationOutbox) -> None:
        """
        Publish outbox payload and mark SENT if publish succeeds.

        This prevents duplicates when a worker later processes PENDING rows.
        """
        if not self._publisher:
            return

        try:
            await self._publisher.publish_json(outbox.topic, dict(outbox.payload or {}))
        except Exception as e:
            logger.warning(f"[notifications] publish failed (outbox stays PENDING): {e}")
            return

        try:
            outbox.status = "SENT"
            outbox.sent_at = datetime.now(timezone.utc)
            outbox.updated_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as e:
            # Publish succeeded but DB update failed: at-least-once semantics still hold.
            logger.warning(f"[notifications] failed to mark outbox SENT: {e}")

    async def get_unread_count(self, db: AsyncSession, *, user_id: str) -> int:
        """Compute unread count (read_at IS NULL)."""
        result = await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
        )
        return int(result.scalar() or 0)

    async def emit_batch(
        self,
        db: AsyncSession,
        *,
        user_ids: list[str],
        category: NotificationCategory,
        title: str,
        body: str,
        data: Optional[dict[str, Any]] = None,
        persist_policy: NotificationPersistPolicy = NotificationPersistPolicy.DURABLE,
        topic: str = DEFAULT_TOPIC,
        idempotency_key_prefix: Optional[str] = None,
        broadcast_id: Optional[str] = None,
    ) -> list[NotificationPublic]:
        """
        A6-FIX: Emit notifications to multiple users with batch DB operations.

        Instead of committing per-user, this method:
        1. Creates all Notification + NotificationOutbox records in memory
        2. Bulk inserts with a single flush
        3. Commits once for the entire batch

        This dramatically reduces DB round-trips for broadcasts (N commits -> 1 commit).

        Returns:
            List of NotificationPublic for DURABLE notifications (empty for VOLATILE)
        """
        if not user_ids:
            return []

        payload_data = data or {}

        # VOLATILE path: publish all without DB writes
        if persist_policy == NotificationPersistPolicy.VOLATILE:
            for user_id in user_ids:
                await self._publish_volatile(
                    user_id=user_id,
                    category=category,
                    title=title,
                    body=body,
                    data=payload_data,
                    topic=topic,
                )
            return []

        # DURABLE path: batch create all records, single commit
        notifications: list[Notification] = []
        outbox_records: list[NotificationOutbox] = []
        now = datetime.now(timezone.utc)

        for user_id in user_ids:
            notification = Notification(
                user_id=user_id,
                category=category.value,
                title=title,
                body=body,
                data=payload_data,
                broadcast_id=broadcast_id,
            )
            notifications.append(notification)
            db.add(notification)

        # Single flush to get all IDs
        await db.flush()

        # Now create outbox records with notification IDs available
        public_notifications: list[NotificationPublic] = []
        for notification in notifications:
            public = self._to_public(notification)
            public_notifications.append(public)

            idem_key = notification.id
            if idempotency_key_prefix:
                idem_key = f"{idempotency_key_prefix}:{notification.user_id}"

            outbox_payload = {
                "version": 1,
                "user_id": notification.user_id,
                "message_type": "notification",
                "data": self._build_ws_message(persisted=True, notification=public),
            }

            outbox = NotificationOutbox(
                idempotency_key=idem_key,
                user_id=notification.user_id,
                topic=topic,
                payload=outbox_payload,
                status="PENDING",
                attempts=0,
                available_at=now,
                broadcast_id=broadcast_id,
            )
            outbox_records.append(outbox)
            db.add(outbox)

        # Single commit for entire batch
        await db.commit()

        # Best-effort publish all (non-blocking, failures stay PENDING for worker)
        for outbox in outbox_records:
            await self._best_effort_publish_and_mark_sent(db=db, outbox=outbox)

        logger.info(f"[notifications] batch emitted {len(notifications)} notifications")
        return public_notifications
