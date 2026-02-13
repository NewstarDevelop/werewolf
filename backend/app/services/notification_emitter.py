"""
NotificationEmitter - Helper for emitting notifications in business events.

This module provides a convenient interface for sending notifications from
API endpoints and business logic. It handles RedisPublisher initialization
and provides async emission patterns.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.notification import NotificationCategory, NotificationPersistPolicy
from app.services.notification_service import NotificationService
from app.services.redis_pubsub import create_redis_client, RedisPublisher

logger = logging.getLogger(__name__)

# Module-level cached publisher (lazy init)
_publisher: Optional[RedisPublisher] = None
_publisher_initialized = False


async def _get_publisher() -> Optional[RedisPublisher]:
    """Get or create RedisPublisher singleton."""
    global _publisher, _publisher_initialized

    if _publisher_initialized:
        return _publisher

    client = await create_redis_client()
    if client:
        _publisher = RedisPublisher(client)
    _publisher_initialized = True

    return _publisher


async def emit_notification(
    db: AsyncSession,
    *,
    user_id: str,
    category: NotificationCategory,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
    persist_policy: NotificationPersistPolicy = NotificationPersistPolicy.DURABLE,
    idempotency_key: Optional[str] = None,
) -> None:
    """
    Emit a notification to a user (async).

    Args:
        db: Database session
        user_id: Target user ID
        category: Notification category (GAME, ROOM, SOCIAL, SYSTEM)
        title: Notification title
        body: Notification body text
        data: Optional additional data
        persist_policy: DURABLE (save to DB) or VOLATILE (real-time only)
        idempotency_key: Optional key to prevent duplicate notifications

    Note:
        This is a best-effort operation. Failures are logged but do not raise exceptions.
    """
    try:
        publisher = await _get_publisher()
        service = NotificationService(publisher=publisher)
        await service.emit(
            db,
            user_id=user_id,
            category=category,
            title=title,
            body=body,
            data=data,
            persist_policy=persist_policy,
            idempotency_key=idempotency_key,
        )
        logger.debug(f"[notifications] emitted {category.value} to user={user_id}")
    except Exception as e:
        logger.warning(f"[notifications] failed to emit notification: {e}")


async def emit_to_users(
    db: AsyncSession,
    *,
    user_ids: list[str],
    category: NotificationCategory,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
    persist_policy: NotificationPersistPolicy = NotificationPersistPolicy.DURABLE,
    idempotency_key_prefix: Optional[str] = None,
    broadcast_id: Optional[str] = None,
) -> None:
    """
    Emit the same notification to multiple users (best-effort).

    A6-FIX: Now uses batch emit for better performance (1 commit vs N commits).

    Args:
        db: Database session
        user_ids: List of target user IDs
        category: Notification category
        title: Notification title
        body: Notification body text
        data: Optional additional data
        persist_policy: DURABLE or VOLATILE
        idempotency_key_prefix: Prefix for idempotency keys (key = prefix:user_id)
        broadcast_id: Optional broadcast ID for admin-sent broadcasts

    Note:
        This is a best-effort operation. Failures are logged but do not raise exceptions.
        Use emit_to_users_strict() if you need to handle failures explicitly.
    """
    if not user_ids:
        return

    try:
        publisher = await _get_publisher()
        service = NotificationService(publisher=publisher)

        # A6-FIX: Use batch emit for single commit instead of per-user commits
        await service.emit_batch(
            db,
            user_ids=user_ids,
            category=category,
            title=title,
            body=body,
            data=data,
            persist_policy=persist_policy,
            idempotency_key_prefix=idempotency_key_prefix,
            broadcast_id=broadcast_id,
        )
        logger.debug(f"[notifications] batch emitted {category.value} to {len(user_ids)} users")
    except Exception as e:
        await db.rollback()
        logger.warning(f"[notifications] batch emit failed: {e}")
        # Best-effort: do not re-raise


async def emit_to_users_strict(
    db: AsyncSession,
    *,
    user_ids: list[str],
    category: NotificationCategory,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
    persist_policy: NotificationPersistPolicy = NotificationPersistPolicy.DURABLE,
    idempotency_key_prefix: Optional[str] = None,
    broadcast_id: Optional[str] = None,
) -> None:
    """
    Emit the same notification to multiple users (strict mode).

    Same as emit_to_users() but raises exceptions on failure.
    Use this when you need to track failures and handle them explicitly.

    Args:
        db: Database session
        user_ids: List of target user IDs
        category: Notification category
        title: Notification title
        body: Notification body text
        data: Optional additional data
        persist_policy: DURABLE or VOLATILE
        idempotency_key_prefix: Prefix for idempotency keys (key = prefix:user_id)
        broadcast_id: Optional broadcast ID for admin-sent broadcasts

    Raises:
        Exception: Re-raises any exception after rollback to allow caller to handle failures
    """
    if not user_ids:
        return

    try:
        publisher = await _get_publisher()
        service = NotificationService(publisher=publisher)

        await service.emit_batch(
            db,
            user_ids=user_ids,
            category=category,
            title=title,
            body=body,
            data=data,
            persist_policy=persist_policy,
            idempotency_key_prefix=idempotency_key_prefix,
            broadcast_id=broadcast_id,
        )
        logger.debug(f"[notifications] batch emitted {category.value} to {len(user_ids)} users")
    except Exception as e:
        await db.rollback()
        logger.warning(f"[notifications] batch emit failed: {e}")
        raise  # Re-raise to allow caller to track failures
