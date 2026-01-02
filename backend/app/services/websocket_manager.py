"""WebSocket connection manager for real-time game updates."""
import logging
from typing import Dict, Set
from fastapi import WebSocket
import json

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for game rooms."""

    def __init__(self):
        # game_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, game_id: str):
        """Accept a new WebSocket connection for a game."""
        await websocket.accept()

        if game_id not in self.active_connections:
            self.active_connections[game_id] = set()

        self.active_connections[game_id].add(websocket)
        logger.info(f"WebSocket connected to game {game_id}. Total connections: {len(self.active_connections[game_id])}")

    def disconnect(self, websocket: WebSocket, game_id: str):
        """Remove a WebSocket connection."""
        if game_id in self.active_connections:
            self.active_connections[game_id].discard(websocket)
            logger.info(f"WebSocket disconnected from game {game_id}. Remaining connections: {len(self.active_connections[game_id])}")

            # Clean up empty game rooms
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]
                logger.info(f"Removed empty game room {game_id}")

    async def send_game_update(self, game_id: str, message: dict):
        """Send a game state update to all connected clients."""
        if game_id not in self.active_connections:
            logger.debug(f"No active connections for game {game_id}")
            return

        # Create list copy to avoid modification during iteration
        connections = list(self.active_connections[game_id])
        disconnected = []

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                disconnected.append(connection)

        # Clean up failed connections
        for connection in disconnected:
            self.disconnect(connection, game_id)

    async def broadcast_to_game(self, game_id: str, event_type: str, data: dict):
        """Broadcast an event to all clients in a game."""
        message = {
            "type": event_type,
            "data": data
        }
        await self.send_game_update(game_id, message)

    def get_connection_count(self, game_id: str) -> int:
        """Get the number of active connections for a game."""
        return len(self.active_connections.get(game_id, set()))


# Global WebSocket manager instance
websocket_manager = ConnectionManager()
