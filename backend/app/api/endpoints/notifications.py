"""Notification REST API endpoints.

Migrated to async database access using SQLAlchemy 2.0 async API.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, update

from app.api.dependencies import get_current_user
from app.core.database_async import get_async_db
from app.models.notification import Notification
from app.schemas.notification import (
    NotificationCategory,
    NotificationListResponse,
    NotificationPublic,
    UnreadCountResponse,
    MarkReadResponse,
    ReadAllResponse,
    ReadBatchRequest,
    ReadBatchResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    category: Optional[NotificationCategory] = Query(None),
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List durable notifications for current user with pagination.

    Sorting:
    - created_at DESC
    """
    user_id = current_user["user_id"]

    # Build WHERE conditions
    conditions = [Notification.user_id == user_id]
    if category:
        conditions.append(Notification.category == category.value)
    if unread_only:
        conditions.append(Notification.read_at.is_(None))

    # Count total
    count_result = await db.execute(
        select(func.count(Notification.id)).where(*conditions)
    )
    total = int(count_result.scalar() or 0)

    # Fetch page
    result = await db.execute(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()

    notifications = [
        NotificationPublic(
            id=n.id,
            user_id=n.user_id,
            category=NotificationCategory(n.category),
            title=n.title,
            body=n.body,
            data=dict(n.data or {}),
            created_at=n.created_at,
            read_at=n.read_at,
        )
        for n in items
    ]

    return NotificationListResponse(
        notifications=notifications,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Return unread durable notification count."""
    user_id = current_user["user_id"]
    result = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    count = int(result.scalar() or 0)
    return UnreadCountResponse(unread_count=count)


@router.post("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Mark one notification as read.

    Security:
    - Only allows updating notifications owned by current user.
    """
    user_id = current_user["user_id"]
    result = await db.execute(
        select(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
    )
    n: Optional[Notification] = result.scalars().first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")

    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        await db.commit()

    return MarkReadResponse(notification_id=n.id, read_at=n.read_at or datetime.now(timezone.utc))


@router.post("/read-all", response_model=ReadAllResponse)
async def mark_all_read(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Mark all unread notifications as read for current user.

    This is implemented as a single SQL UPDATE for performance.
    """
    user_id = current_user["user_id"]
    now = datetime.now(timezone.utc)

    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=now)
    )
    await db.commit()

    return ReadAllResponse(updated=int(result.rowcount or 0), read_at=now)


@router.post("/read-batch", response_model=ReadBatchResponse)
async def mark_batch_read(
    body: ReadBatchRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Mark multiple notifications as read by ID list.

    Security:
    - Only updates notifications owned by current user.
    - Non-existent or other users' notifications are silently ignored.

    Idempotent:
    - Already-read notifications are not modified.
    """
    user_id = current_user["user_id"]
    now = datetime.now(timezone.utc)

    result = await db.execute(
        update(Notification)
        .where(
            Notification.id.in_(body.notification_ids),
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=now)
    )
    await db.commit()

    return ReadBatchResponse(updated=int(result.rowcount or 0), read_at=now)
