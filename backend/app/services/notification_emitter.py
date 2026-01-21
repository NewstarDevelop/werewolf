"""
NotificationEmitter - Helper for emitting notifications in business events.

This module provides a convenient interface for sending notifications from
API endpoints and business logic. It handles RedisPublisher initialization
and provides both sync and async emission patterns.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

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
    db: Session,
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


def emit_notification_sync(
    db: Session,
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
    Emit a notification from synchronous code (fire-and-forget).

    This schedules the async emit on the event loop. Use this in sync API endpoints.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule as a background task
            asyncio.create_task(
                emit_notification(
                    db,
                    user_id=user_id,
                    category=category,
                    title=title,
                    body=body,
                    data=data,
                    persist_policy=persist_policy,
                    idempotency_key=idempotency_key,
                )
            )
        else:
            # Fallback: run in new loop (testing scenarios)
            loop.run_until_complete(
                emit_notification(
                    db,
                    user_id=user_id,
                    category=category,
                    title=title,
                    body=body,
                    data=data,
                    persist_policy=persist_policy,
                    idempotency_key=idempotency_key,
                )
            )
    except Exception as e:
        logger.warning(f"[notifications] sync emit failed: {e}")


async def emit_to_users(
    db: Session,
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
    Emit the same notification to multiple users.

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
    """
    if not user_ids:
        return

    publisher = await _get_publisher()
    service = NotificationService(publisher=publisher)

    for user_id in user_ids:
        try:
            idem_key = f"{idempotency_key_prefix}:{user_id}" if idempotency_key_prefix else None
            await service.emit(
                db,
                user_id=user_id,
                category=category,
                title=title,
                body=body,
                data=data,
                persist_policy=persist_policy,
                idempotency_key=idem_key,
                broadcast_id=broadcast_id,
            )
        except Exception as e:
            db.rollback()
            logger.warning(f"[notifications] failed to emit to user={user_id}: {e}")
