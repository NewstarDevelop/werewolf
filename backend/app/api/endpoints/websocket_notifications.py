"""
WebSocket endpoint: /ws/notifications

Auth (priority order):
1. Cookie: user_access_token (HttpOnly cookie set by /auth/login)
2. Sec-WebSocket-Protocol: auth, <jwt_token> (fallback for non-browser clients)

Requires JWT payload contains user_id (logged-in user).

Delivery:
- Per-instance user connection manager delivers messages to connected clients.
- Cross-instance routing relies on Redis Pub/Sub subscriber (best-effort bootstrap here).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.config import settings
from app.core.database_async import AsyncSessionLocal
from app.models.user import User
from app.services.notification_connection_manager import UserConnectionManager
from app.services.redis_pubsub import create_redis_client, RedisSubscriber
from app.services.notification_service import NotificationService
from app.services.websocket_auth import (
    authenticate_websocket,
    WebSocketAuthError,
    close_with_error,
)

logger = logging.getLogger(__name__)
router = APIRouter()

user_connection_manager = UserConnectionManager()

_redis_task: Optional[asyncio.Task] = None


async def _ensure_redis_subscription_started() -> None:
    """
    Start a per-process Redis subscription task (lazy).

    This keeps changes self-contained without requiring edits in app startup hooks.
    In production, you may prefer explicit startup wiring in app.main.py.
    """
    global _redis_task
    if _redis_task and not _redis_task.done():
        return

    client = await create_redis_client()
    if not client:
        return

    subscriber = RedisSubscriber(client)

    async def handler(message: dict[str, Any]) -> None:
        """
        Route by user_id and forward to WebSocket.

        Expected message format (see schemas.notification.PubSubMessage):
        {
          "version": 1,
          "user_id": "...",
          "message_type": "notification",
          "data": { ... }
        }
        """
        try:
            user_id = str(message.get("user_id") or "")
            message_type = str(message.get("message_type") or "")
            data = message.get("data")
            if not user_id or not message_type or not isinstance(data, dict):
                return
            await user_connection_manager.send_to_user(user_id, message_type, data)
        except Exception as e:
            logger.warning(f"[notifications] redis handler failed: {e}")

    _redis_task = asyncio.create_task(subscriber.run("notifications", handler))
    logger.info("[notifications] redis subscription task started")


@router.websocket("/ws/notifications")
async def notifications_websocket(websocket: WebSocket):
    """
    User-level notification WebSocket.

    Message envelope:
    {
      "type": "connected" | "notification" | "error" | "pong",
      "data": { ... }
    }
    """
    # Unified auth: origin validation + token extraction + verification
    ALLOW_QUERY_TOKEN = getattr(settings, "DEBUG", False)
    try:
        payload = await authenticate_websocket(
            websocket,
            require_auth=True,
            allow_query_token=ALLOW_QUERY_TOKEN,
            validate_origin_header=True,
        )
    except WebSocketAuthError as e:
        logger.warning(f"[notifications] websocket auth failed: {e.message}")
        await close_with_error(websocket, e.code, e.message)
        return

    user_id = payload.get("user_id") if payload else None
    if not user_id:
        await close_with_error(websocket, 4002, "User authentication required")
        return

    # Real-time validation: ensure user exists and is active (same security intent as get_current_user)
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalars().first()
            if not user:
                await close_with_error(websocket, 4004, "User not found")
                return
            if not user.is_active:
                await close_with_error(websocket, 4003, "User disabled")
                return

            # Accept with subprotocol only if client used Sec-WebSocket-Protocol
            subprotocols = websocket.scope.get("subprotocols", [])
            accepted_subprotocol = "auth" if subprotocols and subprotocols[0] == "auth" else None
            await user_connection_manager.connect(user_id, websocket, subprotocol=accepted_subprotocol)

            logger.info(f"[notifications] websocket connected user={user_id}")

            # Start Redis subscription (best-effort)
            await _ensure_redis_subscription_started()

            # Send initial state (unread count)
            service = NotificationService(publisher=None)
            unread = await service.get_unread_count(db, user_id=user_id)

            await websocket.send_json(
                {
                    "type": "connected",
                    "data": {"user_id": user_id, "unread_count": unread},
                }
            )

            # Keep alive loop (same ping/pong convention as existing endpoints)
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")

        except WebSocketDisconnect:
            logger.info(f"[notifications] websocket disconnected user={user_id}")
        except Exception as e:
            logger.error(f"[notifications] websocket error user={user_id}: {e}", exc_info=True)
        finally:
            try:
                await user_connection_manager.disconnect(user_id, websocket)
            except Exception:
                pass
