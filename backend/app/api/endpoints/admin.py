"""Admin management endpoints."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import verify_admin
from app.core.database_async import get_async_db
from app.models.user import User
from app.schemas.admin import (
    BroadcastNotificationRequest,
    BroadcastNotificationResponse,
    RestartResponse,
)
from app.services.notification_emitter import emit_to_users

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

DEFAULT_BROADCAST_PAGE_SIZE = 500


def _send_sigterm():
    """Send SIGTERM to self for graceful shutdown."""
    try:
        os.kill(os.getpid(), signal.SIGTERM)
    except Exception as e:
        logger.error(f"Failed to send SIGTERM: {e}, pid={os.getpid()}")


@router.post("/restart", response_model=RestartResponse, status_code=202)
async def restart_service(
    request: Request,
    actor: Dict = Depends(verify_admin),
):
    """
    Trigger graceful service restart.
    POST /api/admin/restart

    Security: Admin only (JWT admin token)
    The actual restart is handled by external process manager (docker/systemd).
    """
    client_ip: Optional[str] = None
    try:
        if request.client:
            client_ip = request.client.host
    except Exception:
        client_ip = "unknown"

    actor_id = actor.get("player_id", "unknown")

    logger.warning(f"RESTART_REQUESTED by actor={actor_id} from ip={client_ip}")

    # Schedule SIGTERM after 1s on the event loop (non-blocking, no threadpool)
    loop = asyncio.get_running_loop()
    loop.call_later(1, _send_sigterm)

    return RestartResponse(
        status="accepted",
        message="Restart scheduled. Service will restart in ~1 second.",
        delay_seconds=1,
    )


@router.post(
    "/notifications/broadcast",
    response_model=BroadcastNotificationResponse,
    status_code=202,
)
async def broadcast_notifications(
    request: Request,
    body: BroadcastNotificationRequest,
    actor: Dict = Depends(verify_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Broadcast a notification to all registered users.
    POST /api/admin/notifications/broadcast

    Security: Admin only (JWT admin token)
    """
    client_ip: Optional[str] = None
    try:
        if request.client:
            client_ip = request.client.host
    except Exception:
        client_ip = "unknown"

    actor_id = actor.get("player_id", "unknown")
    logger.warning(
        "BROADCAST_REQUESTED actor=%s ip=%s idem=%s category=%s",
        actor_id,
        client_ip,
        body.idempotency_key,
        body.category.value,
    )

    # Query active users with pagination
    count_result = await db.execute(
        select(func.count(User.id)).where(User.is_active.is_(True))
    )
    total_targets = int(count_result.scalar() or 0)
    processed = 0
    offset = 0

    while True:
        result = await db.execute(
            select(User.id)
            .where(User.is_active.is_(True))
            .order_by(User.id)
            .offset(offset)
            .limit(DEFAULT_BROADCAST_PAGE_SIZE)
        )
        user_ids = [row[0] for row in result.all()]
        if not user_ids:
            break

        await emit_to_users(
            db,
            user_ids=user_ids,
            category=body.category,
            title=body.title,
            body=body.body,
            data=body.data,
            persist_policy=body.persist_policy,
            idempotency_key_prefix=body.idempotency_key,
        )
        processed += len(user_ids)
        offset += DEFAULT_BROADCAST_PAGE_SIZE

    logger.warning(
        "BROADCAST_COMPLETED actor=%s ip=%s idem=%s processed=%s total=%s",
        actor_id,
        client_ip,
        body.idempotency_key,
        processed,
        total_targets,
    )

    return BroadcastNotificationResponse(
        status="accepted",
        idempotency_key=body.idempotency_key,
        total_targets=total_targets,
        processed=processed,
    )
