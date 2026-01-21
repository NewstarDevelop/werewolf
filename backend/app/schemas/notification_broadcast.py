"""NotificationBroadcast schemas (Pydantic)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .notification import NotificationCategory, NotificationPersistPolicy


class BroadcastStatus(str, Enum):
    """Broadcast lifecycle status."""

    DRAFT = "DRAFT"
    SENDING = "SENDING"
    SENT = "SENT"
    PARTIAL_FAILED = "PARTIAL_FAILED"
    FAILED = "FAILED"
    DELETED = "DELETED"


class ResendScope(str, Enum):
    """Scope for resend operation."""

    ALL_ACTIVE = "all_active"
    FAILED_ONLY = "failed_only"


class DeleteMode(str, Enum):
    """Mode for delete operation."""

    HISTORY = "history"
    CASCADE = "cascade"


class BatchAction(str, Enum):
    """Available batch actions."""

    DELETE = "delete"


# =============================================================================
# Request Schemas
# =============================================================================


class BroadcastCreateRequest(BaseModel):
    """Request to create and optionally send a broadcast."""

    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    category: NotificationCategory = Field(default=NotificationCategory.SYSTEM)
    data: dict[str, Any] = Field(default_factory=dict)
    persist_policy: NotificationPersistPolicy = Field(default=NotificationPersistPolicy.DURABLE)
    idempotency_key: str = Field(..., min_length=8, max_length=128)
    send_now: bool = Field(default=True, description="If true, send immediately; if false, save as draft")


class BroadcastUpdateRequest(BaseModel):
    """Request to update a draft broadcast."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    body: Optional[str] = Field(None, min_length=1, max_length=2000)
    category: Optional[NotificationCategory] = None
    data: Optional[dict[str, Any]] = None
    persist_policy: Optional[NotificationPersistPolicy] = None


class BroadcastResendRequest(BaseModel):
    """Request to resend a broadcast."""

    scope: ResendScope = Field(default=ResendScope.ALL_ACTIVE)
    idempotency_key: str = Field(..., min_length=8, max_length=128)


class BroadcastBatchRequest(BaseModel):
    """Request for batch operations."""

    action: BatchAction
    ids: list[str] = Field(..., min_length=1, max_length=100)
    mode: DeleteMode = Field(default=DeleteMode.HISTORY)


# =============================================================================
# Response Schemas
# =============================================================================


class BroadcastListItem(BaseModel):
    """Broadcast item for list view (summary)."""

    id: str
    title: str
    category: NotificationCategory
    status: BroadcastStatus
    total_targets: int
    sent_count: int
    failed_count: int
    created_at: datetime
    sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BroadcastDetail(BaseModel):
    """Full broadcast detail."""

    id: str
    idempotency_key: str
    title: str
    body: str
    category: NotificationCategory
    data: dict[str, Any] = Field(default_factory=dict)
    persist_policy: NotificationPersistPolicy
    status: BroadcastStatus
    total_targets: int
    processed: int
    sent_count: int
    failed_count: int
    created_by: Optional[str] = None
    resend_of_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    last_error: Optional[str] = None

    class Config:
        from_attributes = True


class BroadcastListResponse(BaseModel):
    """Paginated broadcast list response."""

    items: list[BroadcastListItem]
    total: int
    page: int
    page_size: int


class BroadcastCreateResponse(BaseModel):
    """Response after creating a broadcast."""

    id: str
    status: BroadcastStatus
    total_targets: int
    processed: int


class BroadcastBatchResponse(BaseModel):
    """Response for batch operations."""

    accepted: int
    updated: int
    failed: list[str] = Field(default_factory=list)
