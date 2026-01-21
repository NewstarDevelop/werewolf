"""
Notification models.

This module defines:
- Notification: durable notifications stored in DB (history + read/unread)
- NotificationOutbox: outbox rows for reliable cross-instance delivery (Redis Pub/Sub)
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Text,
    ForeignKey,
    Index,
    CheckConstraint,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict

from .base import Base


class Notification(Base):
    """
    Durable notification stored in DB.

    Notes:
    - UUIDs are stored as String(36) to match existing models (e.g. users.id).
    - read_at is NULL => unread; non-NULL => read.
    - data is JSON for extensibility (room_id/game_id/action_url/etc).
    - broadcast_id links to NotificationBroadcast for admin-sent broadcasts.
    """

    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broadcast_id = Column(
        String(36),
        ForeignKey("notification_broadcasts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    category = Column(String(16), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)

    data = Column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
        server_default="{}",
    )

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at = Column(DateTime, nullable=True, index=True)

    # Keep relationship optional (no back_populates requirement on User model)
    user = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "category IN ('GAME','ROOM','SOCIAL','SYSTEM')",
            name="ck_notifications_category",
        ),
        Index("idx_notifications_user_created_at", "user_id", "created_at"),
        Index("idx_notifications_user_read_at_created_at", "user_id", "read_at", "created_at"),
    )


class NotificationOutbox(Base):
    """
    Outbox table for reliable delivery.

    Workflow:
    - Business transaction inserts Notification (optional) + NotificationOutbox(status=PENDING)
    - A worker (or an in-process scheduler) claims rows (SKIP LOCKED in PostgreSQL)
    - Worker publishes payload to Redis Pub/Sub and marks SENT / retries with backoff

    Important:
    - At-least-once semantics; consumers should be idempotent (dedupe by notification.id).
    - broadcast_id links to NotificationBroadcast for admin-sent broadcasts.
    """

    __tablename__ = "notification_outbox"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Unique idempotency key prevents duplicate outbox events (e.g. notification.id or business key)
    idempotency_key = Column(String(255), nullable=False, unique=True, index=True)

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broadcast_id = Column(
        String(36),
        ForeignKey("notification_broadcasts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    topic = Column(String(64), nullable=False, default="notifications")

    # Payload is the message that will be published to Redis; keep it self-contained for workers.
    payload = Column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
        server_default="{}",
    )

    status = Column(String(16), nullable=False, default="PENDING", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    locked_at = Column(DateTime, nullable=True, index=True)
    locked_by = Column(String(128), nullable=True)

    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)

    user = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','SENT','FAILED')",
            name="ck_notification_outbox_status",
        ),
        Index("idx_notification_outbox_pending", "status", "available_at", "created_at"),
    )
