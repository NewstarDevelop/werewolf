"""WebSocket connection manager for real-time game updates."""
import asyncio
import logging
from typing import Dict, Tuple, Set, Optional, Callable
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages per-player WebSocket connections for game rooms."""

    MAX_CONNECTIONS_PER_GAME = 20
    MAX_TOTAL_CONNECTIONS = 500

    def __init__(self):
        # (game_id, player_id) -> WebSocket for precise player routing
        self.connections: Dict[Tuple[str, str], WebSocket] = {}
        # game_id -> set of player_ids (auxiliary index for broadcasts)
        self._game_players: Dict[str, Set[str]] = {}

    async def connect(self, game_id: str, player_id: str, websocket: WebSocket, subprotocol: str = None):
        """Accept a new WebSocket connection for a specific player in a game.

        Args:
            game_id: The game identifier
            player_id: The player identifier
            websocket: The WebSocket connection
            subprotocol: Optional subprotocol to accept (for Sec-WebSocket-Protocol)
        """
        key = (game_id, player_id)
        existing = self.connections.get(key)

        # Enforce connection limits (skip check if reconnecting same player)
        if not existing:
            total = self.get_total_connection_count()
            if total >= self.MAX_TOTAL_CONNECTIONS:
                logger.warning(f"Global connection limit reached ({total}). Rejecting {player_id} for {game_id}")
                await websocket.close(code=1013, reason="Server overloaded")
                return
            game_count = self.get_connection_count(game_id)
            if game_count >= self.MAX_CONNECTIONS_PER_GAME:
                logger.warning(f"Per-game connection limit reached ({game_count}) for {game_id}. Rejecting {player_id}")
                await websocket.close(code=1013, reason="Too many connections for this game")
                return

        await websocket.accept(subprotocol=subprotocol)
        self.connections[key] = websocket

        if game_id not in self._game_players:
            self._game_players[game_id] = set()
        self._game_players[game_id].add(player_id)

        logger.info(f"Player {player_id} connected to game {game_id}. Total players: {len(self._game_players[game_id])}")
        if existing and existing is not websocket:
            try:
                await existing.close(code=1000)
            except Exception:
                pass

    def disconnect(self, game_id: str, player_id: str, websocket: Optional[WebSocket] = None):
        """Disconnect a specific player's WebSocket."""
        key = (game_id, player_id)
        current = self.connections.get(key)
        if current and (websocket is None or current is websocket):
            del self.connections[key]

        if game_id in self._game_players:
            # Only drop the player index if we actually removed the active connection
            if current and (websocket is None or current is websocket):
                self._game_players[game_id].discard(player_id)
                if not self._game_players[game_id]:
                    del self._game_players[game_id]
                    logger.info(f"Removed empty game room {game_id}")

        logger.info(f"Player {player_id} disconnected from game {game_id}")

    async def send_to_player(
        self,
        game_id: str,
        player_id: str,
        message_type: str,
        data: dict
    ):
        """Send a message to a specific player."""
        ws = self.connections.get((game_id, player_id))
        if ws:
            try:
                await ws.send_json({
                    "type": message_type,
                    "data": data
                })
            except Exception as e:
                logger.error(f"Failed to send to player {player_id} in game {game_id}: {e}")
                try:
                    await ws.close(code=1011)
                except Exception:
                    pass
                self.disconnect(game_id, player_id, ws)

    async def broadcast_to_game_players(
        self,
        game_id: str,
        message_type: str,
        state_builder: Callable[[str], dict]
    ):
        """
        Broadcast to all players in a game with per-player state filtering.

        Args:
            game_id: Game identifier
            message_type: Message type (e.g., "game_update")
            state_builder: Function that takes player_id and returns player-specific state
        """
        if game_id not in self._game_players:
            logger.debug(f"No active connections for game {game_id}")
            return

        # PERF-FIX: Build states and send in parallel using asyncio.gather
        async def _send_to_one(pid: str):
            try:
                player_state = state_builder(pid)
                await self.send_to_player(game_id, pid, message_type, player_state)
            except Exception as e:
                logger.error(f"Failed to build/send state for player {pid}: {e}")

        tasks = [_send_to_one(pid) for pid in list(self._game_players[game_id])]
        if tasks:
            await asyncio.gather(*tasks)

    async def broadcast_to_game(self, game_id: str, event_type: str, data: dict):
        """
        Legacy broadcast method (sends same data to all players).
        Use for single-player mode or non-role-sensitive updates.
        """
        if game_id not in self._game_players:
            return

        # PERF-FIX: Send in parallel
        tasks = [
            self.send_to_player(game_id, pid, event_type, data)
            for pid in list(self._game_players[game_id])
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_connection_count(self, game_id: str) -> int:
        """Get the number of active connections for a game."""
        return len(self._game_players.get(game_id, set()))

    def get_total_connection_count(self) -> int:
        """Get the total number of active game WebSocket connections."""
        # Use list() snapshot to avoid "dictionary changed size during iteration"
        return sum(len(players) for players in list(self._game_players.values()))

    def get_active_game_ids(self) -> list[str]:
        """List game_ids that currently have active WebSocket connections."""
        # Use list() snapshot to avoid "dictionary changed size during iteration"
        return [gid for gid, players in list(self._game_players.items()) if players]


# Global WebSocket manager instance
websocket_manager = ConnectionManager()
