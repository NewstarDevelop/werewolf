"""Cross-instance game state broadcaster using Redis Pub/Sub.

When multiple server instances share game state via RedisBackend,
this broadcaster ensures that a state change on instance A triggers
WebSocket updates to players connected on instance B.

Architecture:
    Instance A: game state change → broadcast locally + publish to Redis channel
    Instance B: Redis subscriber → receive notification → broadcast to local connections

Falls back to local-only broadcasting when Redis is not available.
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.websocket_manager import ConnectionManager

logger = logging.getLogger(__name__)

# Unique instance ID to avoid processing own broadcasts
_INSTANCE_ID = str(uuid.uuid4())[:8]

CHANNEL_PREFIX = "werewolf:game_broadcast:"


class GameUpdateBroadcaster:
    """Handles cross-instance game state broadcasting via Redis Pub/Sub.

    Usage:
        broadcaster = GameUpdateBroadcaster(websocket_manager)
        await broadcaster.start()  # Start subscriber loop

        # After game state change:
        await broadcaster.broadcast_game_update(game_id, game)

        await broadcaster.stop()  # Shutdown
    """

    def __init__(self, connection_manager: "ConnectionManager"):
        self._ws_manager = connection_manager
        self._redis_client = None
        self._subscriber_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._instance_id = _INSTANCE_ID

    async def start(self) -> None:
        """Initialize Redis client and start subscriber loop if Redis is available."""
        try:
            import redis.asyncio as aioredis
            redis_url = os.getenv("REDIS_URL", "").strip()
            if not redis_url:
                logger.info("[broadcaster] No REDIS_URL, local-only mode")
                return
            self._redis_client = aioredis.Redis.from_url(
                redis_url, decode_responses=True
            )
            await self._redis_client.ping()
            self._subscriber_task = asyncio.create_task(self._subscriber_loop())
            logger.info("[broadcaster] Started cross-instance broadcaster (instance=%s)", self._instance_id)
        except Exception as e:
            logger.warning("[broadcaster] Redis unavailable, local-only mode: %s", e)
            self._redis_client = None

    async def stop(self) -> None:
        """Shutdown subscriber loop and close Redis connection."""
        self._stop_event.set()
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._redis_client:
            try:
                await self._redis_client.aclose()
            except Exception:
                pass
        logger.info("[broadcaster] Stopped")

    async def publish_game_update(self, game_id: str) -> None:
        """Publish a game update notification to Redis for other instances.

        Called after broadcasting to local connections. Other instances
        will pick up this notification and broadcast to their local players.
        """
        if not self._redis_client:
            return
        try:
            channel = f"{CHANNEL_PREFIX}{game_id}"
            payload = json.dumps({
                "game_id": game_id,
                "source": self._instance_id,
            }, separators=(",", ":"))
            await self._redis_client.publish(channel, payload)
        except Exception as e:
            logger.warning("[broadcaster] Failed to publish update for game %s: %s", game_id, e)

    async def _subscriber_loop(self) -> None:
        """Subscribe to game update channels and handle notifications."""
        if not self._redis_client:
            return

        pubsub = self._redis_client.pubsub()
        try:
            # Subscribe to all game broadcast channels via pattern
            await pubsub.psubscribe(f"{CHANNEL_PREFIX}*")
            logger.info("[broadcaster] Subscribed to %s*", CHANNEL_PREFIX)

            while not self._stop_event.is_set():
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0
                    )
                    if message and message.get("type") == "pmessage":
                        await self._handle_message(message)
                    else:
                        await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning("[broadcaster] Subscriber error: %s", e)
                    await asyncio.sleep(1.0)
        finally:
            try:
                await pubsub.punsubscribe(f"{CHANNEL_PREFIX}*")
                await pubsub.aclose()
            except Exception:
                pass

    async def _handle_message(self, message: dict) -> None:
        """Handle an incoming game update notification from another instance."""
        try:
            raw = message.get("data", "")
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")
            payload = json.loads(raw)

            # Skip our own broadcasts
            if payload.get("source") == self._instance_id:
                return

            game_id = payload.get("game_id")
            if not game_id:
                return

            # Only broadcast if we have local connections for this game
            if not self._ws_manager.get_connection_count(game_id):
                return

            logger.debug(
                "[broadcaster] Received update for game %s from instance %s",
                game_id, payload.get("source")
            )

            # Fetch latest game state and broadcast to local connections
            from app.models.game import game_store
            game = game_store.get_game(game_id)
            if not game:
                return

            if game.player_mapping:
                await self._ws_manager.broadcast_to_game_players(
                    game_id,
                    "game_update",
                    lambda pid: game.get_state_for_player(pid)
                )
            else:
                full_state = game.get_state_for_player(None)
                await self._ws_manager.broadcast_to_game(
                    game_id, "game_update", full_state
                )
        except Exception as e:
            logger.warning("[broadcaster] Failed to handle message: %s", e)


# Global instance (initialized in app startup)
game_broadcaster: Optional[GameUpdateBroadcaster] = None
