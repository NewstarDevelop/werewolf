"""
NotificationBroadcast model.

This module defines the NotificationBroadcast entity for tracking broadcast events
sent by administrators, supporting history management, resend, and batch operations.
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


class NotificationBroadcast(Base):
    """
    Broadcast event entity for admin notification management.

    Status lifecycle:
    - DRAFT -> SENDING -> SENT
    - SENDING -> PARTIAL_FAILED (some failed)
    - SENDING -> FAILED (all failed)
    - Any status -> DELETED (soft delete)

    Notes:
    - Each broadcast creates one NotificationBroadcast record
    - Individual notifications reference this via broadcast_id
    - Supports resend via resend_of_id foreign key to original broadcast
    """

    __tablename__ = "notification_broadcasts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)

    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    category = Column(String(16), nullable=False, index=True)

    data = Column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
        server_default="{}",
    )

    persist_policy = Column(String(16), nullable=False, default="DURABLE")
    status = Column(String(16), nullable=False, default="DRAFT", index=True)

    # Statistics
    total_targets = Column(Integer, nullable=False, default=0)
    processed = Column(Integer, nullable=False, default=0)
    sent_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)

    # Audit fields
    created_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resend_of_id = Column(
        String(36),
        ForeignKey("notification_broadcasts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    sent_at = Column(DateTime, nullable=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)

    # Error tracking
    last_error = Column(Text, nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    resend_of = relationship("NotificationBroadcast", remote_side=[id], foreign_keys=[resend_of_id])

    __table_args__ = (
        CheckConstraint(
            "category IN ('GAME','ROOM','SOCIAL','SYSTEM')",
            name="ck_notification_broadcasts_category",
        ),
        CheckConstraint(
            "persist_policy IN ('DURABLE','VOLATILE')",
            name="ck_notification_broadcasts_persist_policy",
        ),
        CheckConstraint(
            "status IN ('DRAFT','SENDING','SENT','PARTIAL_FAILED','FAILED','DELETED')",
            name="ck_notification_broadcasts_status",
        ),
        Index("idx_notification_broadcasts_status_created_at", "status", "created_at"),
        Index("idx_notification_broadcasts_category_created_at", "category", "created_at"),
    )
