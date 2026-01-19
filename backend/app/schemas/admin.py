"""Admin-related schemas."""

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.notification import NotificationCategory, NotificationPersistPolicy


class RestartResponse(BaseModel):
    """Response for restart endpoint."""

    status: str
    message: str
    delay_seconds: int


class BroadcastNotificationRequest(BaseModel):
    """Request payload for admin broadcast notifications."""

    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    category: NotificationCategory = Field(default=NotificationCategory.SYSTEM)
    data: dict[str, Any] = Field(default_factory=dict)
    persist_policy: NotificationPersistPolicy = Field(
        default=NotificationPersistPolicy.DURABLE
    )
    idempotency_key: str = Field(..., min_length=8, max_length=128)


class BroadcastNotificationResponse(BaseModel):
    """Response payload for admin broadcast notifications."""

    status: str
    idempotency_key: str
    total_targets: int
    processed: int
