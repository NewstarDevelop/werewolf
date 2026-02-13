"""Game state persistence service.

Provides SQLite-backed snapshots for crash recovery of in-memory game state.
Uses a write-behind pattern: in-memory GameStore remains the primary store,
snapshots are saved asynchronously on key state changes.
"""
import json
import logging
import sqlite3
import os
import time
import threading
from typing import Optional, TYPE_CHECKING
from dataclasses import asdict

from app.core.config import settings
from app.schemas.enums import (
    GameStatus, GamePhase, Role, ActionType, MessageType, Winner
)

if TYPE_CHECKING:
    from app.models.game import Game, Player, Message, Action

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_game(game: "Game") -> dict:
    """Serialize a Game dataclass to a JSON-compatible dict."""
    from app.models.game import Game

    data = {
        "id": game.id,
        "status": game.status.value,
        "day": game.day,
        "phase": game.phase.value,
        "winner": game.winner.value if game.winner else None,
        "language": game.language,
        "state_version": game.state_version,
        "current_actor_seat": game.current_actor_seat,
        "human_seat": game.human_seat,
        "human_seats": game.human_seats,
        "player_mapping": game.player_mapping,
        # Night phase
        "night_kill_target": game.night_kill_target,
        "wolf_votes": {str(k): v for k, v in game.wolf_votes.items()},
        "wolf_chat_completed": list(game.wolf_chat_completed),
        "wolf_night_plan": game.wolf_night_plan,
        "guard_target": game.guard_target,
        "guard_last_target": game.guard_last_target,
        "guard_decided": game.guard_decided,
        "white_wolf_king_used_explode": game.white_wolf_king_used_explode,
        "white_wolf_king_explode_target": game.white_wolf_king_explode_target,
        "seer_verified_this_night": game.seer_verified_this_night,
        "witch_save_decided": game.witch_save_decided,
        "witch_poison_decided": game.witch_poison_decided,
        # Day phase
        "day_votes": {str(k): v for k, v in game.day_votes.items()},
        "speech_order": game.speech_order,
        "current_speech_index": game.current_speech_index,
        "_spoken_seats_this_round": list(game._spoken_seats_this_round),
        # Deaths
        "pending_deaths": game.pending_deaths,
        "pending_deaths_unblockable": game.pending_deaths_unblockable,
        "last_night_deaths": game.last_night_deaths,
        # Counters
        "_message_counter": game._message_counter,
        "_action_counter": game._action_counter,
        # Nested
        "players": {str(k): _serialize_player(v) for k, v in game.players.items()},
        "messages": [_serialize_message(m) for m in game.messages],
        "actions": [_serialize_action(a) for a in game.actions],
    }
    return data


def _serialize_player(player: "Player") -> dict:
    return {
        "seat_id": player.seat_id,
        "role": player.role.value,
        "is_human": player.is_human,
        "is_alive": player.is_alive,
        "personality": player.personality.model_dump() if player.personality else None,
        "has_save_potion": player.has_save_potion,
        "has_poison_potion": player.has_poison_potion,
        "can_shoot": player.can_shoot,
        "verified_players": {str(k): v for k, v in player.verified_players.items()},
        "teammates": player.teammates,
        "wolf_persona": player.wolf_persona,
        "user_id": player.user_id,
    }


def _serialize_message(msg: "Message") -> dict:
    return {
        "id": msg.id,
        "game_id": msg.game_id,
        "day": msg.day,
        "seat_id": msg.seat_id,
        "content": msg.content,
        "msg_type": msg.msg_type.value,
    }


def _serialize_action(action: "Action") -> dict:
    return {
        "id": action.id,
        "game_id": action.game_id,
        "day": action.day,
        "phase": action.phase,
        "player_id": action.player_id,
        "action_type": action.action_type.value,
        "target_id": action.target_id,
    }


# ---------------------------------------------------------------------------
# Deserialization helpers
# ---------------------------------------------------------------------------

def _deserialize_game(data: dict) -> "Game":
    """Deserialize a dict back into a Game dataclass."""
    from app.models.game import Game, Player, Message, Action
    from app.schemas.player import Personality

    game = Game(id=data["id"], language=data.get("language", "zh"))
    game.status = GameStatus(data["status"])
    game.day = data["day"]
    game.phase = GamePhase(data["phase"])
    game.winner = Winner(data["winner"]) if data.get("winner") else None
    game.state_version = data.get("state_version", 0)
    game.current_actor_seat = data.get("current_actor_seat")
    game.human_seat = data.get("human_seat", 1)
    game.human_seats = data.get("human_seats", [])
    game.player_mapping = data.get("player_mapping", {})

    # Night phase
    game.night_kill_target = data.get("night_kill_target")
    game.wolf_votes = {int(k): v for k, v in data.get("wolf_votes", {}).items()}
    game.wolf_chat_completed = set(data.get("wolf_chat_completed", []))
    game.wolf_night_plan = data.get("wolf_night_plan")
    game.guard_target = data.get("guard_target")
    game.guard_last_target = data.get("guard_last_target")
    game.guard_decided = data.get("guard_decided", False)
    game.white_wolf_king_used_explode = data.get("white_wolf_king_used_explode", False)
    game.white_wolf_king_explode_target = data.get("white_wolf_king_explode_target")
    game.seer_verified_this_night = data.get("seer_verified_this_night", False)
    game.witch_save_decided = data.get("witch_save_decided", False)
    game.witch_poison_decided = data.get("witch_poison_decided", False)

    # Day phase
    game.day_votes = {int(k): v for k, v in data.get("day_votes", {}).items()}
    game.speech_order = data.get("speech_order", [])
    game.current_speech_index = data.get("current_speech_index", 0)
    game._spoken_seats_this_round = set(data.get("_spoken_seats_this_round", []))

    # Deaths
    game.pending_deaths = data.get("pending_deaths", [])
    game.pending_deaths_unblockable = data.get("pending_deaths_unblockable", [])
    game.last_night_deaths = data.get("last_night_deaths", [])

    # Counters
    game._message_counter = data.get("_message_counter", 0)
    game._action_counter = data.get("_action_counter", 0)

    # Players
    for seat_str, p_data in data.get("players", {}).items():
        personality = None
        if p_data.get("personality"):
            personality = Personality(**p_data["personality"])
        player = Player(
            seat_id=p_data["seat_id"],
            role=Role(p_data["role"]),
            is_human=p_data.get("is_human", False),
            is_alive=p_data.get("is_alive", True),
            personality=personality,
            has_save_potion=p_data.get("has_save_potion", True),
            has_poison_potion=p_data.get("has_poison_potion", True),
            can_shoot=p_data.get("can_shoot", True),
            verified_players={int(k): v for k, v in p_data.get("verified_players", {}).items()},
            teammates=p_data.get("teammates", []),
            wolf_persona=p_data.get("wolf_persona"),
            user_id=p_data.get("user_id"),
        )
        game.players[int(seat_str)] = player

    # Messages
    for m_data in data.get("messages", []):
        msg = Message(
            id=m_data["id"],
            game_id=m_data["game_id"],
            day=m_data["day"],
            seat_id=m_data["seat_id"],
            content=m_data["content"],
            msg_type=MessageType(m_data["msg_type"]),
        )
        game.messages.append(msg)

    # Actions
    for a_data in data.get("actions", []):
        action = Action(
            id=a_data["id"],
            game_id=a_data["game_id"],
            day=a_data["day"],
            phase=a_data["phase"],
            player_id=a_data["player_id"],
            action_type=ActionType(a_data["action_type"]),
            target_id=a_data.get("target_id"),
        )
        game.actions.append(action)

    return game


# ---------------------------------------------------------------------------
# Persistence service
# ---------------------------------------------------------------------------

class GamePersistence:
    """SQLite-backed game state persistence for crash recovery.

    Design:
    - Uses a dedicated SQLite file (not the main app DB) to avoid schema conflicts
    - Saves game snapshots as JSON blobs on key state changes
    - Loads all active snapshots on startup for crash recovery
    - Cleans up finished/expired game snapshots automatically
    """

    SNAPSHOT_TTL_SECONDS = 7200  # Match GameStore TTL

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(settings.DATA_DIR, "game_snapshots.db")
        self._db_path = db_path
        self._initialized = False
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        """Get the shared SQLite connection, initializing schema if needed.

        Must be called while holding self._lock.
        """
        if self._conn is None:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        if not self._initialized:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS game_snapshots (
                    game_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            self._conn.commit()
            self._initialized = True
        return self._conn

    def save_snapshot(self, game: "Game") -> None:
        """Save a game state snapshot."""
        try:
            data = _serialize_game(game)
            state_json = json.dumps(data, ensure_ascii=False)
            with self._lock:
                conn = self._get_conn()
                conn.execute(
                    """INSERT OR REPLACE INTO game_snapshots
                       (game_id, state_json, status, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (game.id, state_json, game.status.value, time.time())
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to save game snapshot {game.id}: {e}")

    def delete_snapshot(self, game_id: str) -> None:
        """Delete a game snapshot."""
        try:
            with self._lock:
                conn = self._get_conn()
                conn.execute("DELETE FROM game_snapshots WHERE game_id = ?", (game_id,))
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to delete game snapshot {game_id}: {e}")

    def load_all_active(self) -> dict[str, "Game"]:
        """Load all active (non-finished, non-expired) game snapshots.

        Returns:
            Dict mapping game_id -> Game for crash recovery.
        """
        games = {}
        try:
            with self._lock:
                conn = self._get_conn()
                cutoff = time.time() - self.SNAPSHOT_TTL_SECONDS
                cursor = conn.execute(
                    """SELECT game_id, state_json FROM game_snapshots
                       WHERE status != ? AND updated_at > ?""",
                    (GameStatus.FINISHED.value, cutoff)
                )
                for row in cursor.fetchall():
                    game_id, state_json = row
                    try:
                        data = json.loads(state_json)
                        game = _deserialize_game(data)
                        games[game_id] = game
                    except Exception as e:
                        logger.warning(f"Failed to deserialize game {game_id}: {e}")

                # Clean up expired/finished snapshots
                conn.execute(
                    "DELETE FROM game_snapshots WHERE updated_at <= ?",
                    (cutoff,)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to load game snapshots: {e}")
        return games

    def cleanup_finished(self) -> int:
        """Remove snapshots for finished games."""
        try:
            with self._lock:
                conn = self._get_conn()
                cursor = conn.execute(
                    "DELETE FROM game_snapshots WHERE status = ?",
                    (GameStatus.FINISHED.value,)
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.warning(f"Failed to cleanup finished snapshots: {e}")
            return 0


# Global instance (lazily used by GameStore)
game_persistence = GamePersistence()
