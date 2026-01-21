"""Notification schemas (Pydantic)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import Field

from app.schemas.base import UTCZBaseModel, UTCZFromAttributesModel


class NotificationCategory(str, Enum):
    """Business category for filtering and UI grouping."""

    GAME = "GAME"
    ROOM = "ROOM"
    SOCIAL = "SOCIAL"
    SYSTEM = "SYSTEM"


class NotificationPersistPolicy(str, Enum):
    """
    Storage policy (tiered storage).

    - VOLATILE: real-time only (toast), not stored
    - DURABLE: stored in DB + outbox + real-time push
    """

    VOLATILE = "VOLATILE"
    DURABLE = "DURABLE"


class NotificationPublic(UTCZFromAttributesModel):
    """Public notification payload returned by REST APIs."""

    id: str
    user_id: str
    category: NotificationCategory
    title: str
    body: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    read_at: Optional[datetime] = None


class NotificationListResponse(UTCZBaseModel):
    """Paginated notification list response."""

    notifications: list[NotificationPublic]
    total: int
    page: int
    page_size: int


class UnreadCountResponse(UTCZBaseModel):
    """Unread count response."""

    unread_count: int


class MarkReadResponse(UTCZBaseModel):
    """Mark-one-as-read response."""

    notification_id: str
    read_at: datetime


class ReadAllResponse(UTCZBaseModel):
    """Mark-all-as-read response."""

    updated: int
    read_at: datetime


class ReadBatchRequest(UTCZBaseModel):
    """Batch mark-as-read request."""

    notification_ids: list[str] = Field(..., min_length=1, max_length=100)


class ReadBatchResponse(UTCZBaseModel):
    """Batch mark-as-read response."""

    updated: int
    read_at: datetime


class NotificationMessageData(UTCZBaseModel):
    """
    Data field inside WebSocket envelope for notification messages.

    This keeps the WebSocket envelope consistent with existing style:
    { "type": "<message_type>", "data": { ... } }
    """

    persisted: bool
    notification: Optional[NotificationPublic] = None
    event_id: Optional[str] = None  # for volatile messages without DB id


class PubSubMessage(UTCZBaseModel):
    """
    Redis Pub/Sub message schema.

    The subscriber routes by user_id and forwards to WebSocket via:
    send_to_user(user_id, message_type, data).
    """

    version: int = 1
    user_id: str
    message_type: str
    data: dict[str, Any]
