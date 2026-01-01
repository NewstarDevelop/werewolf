"""Game logging service - captures and filters game logs."""
import logging
import time
from typing import List, Dict, Optional
from collections import deque
from datetime import datetime

# Store logs per game ID
game_logs: Dict[str, deque] = {}

# Sensitive keywords to filter out (to avoid spoilers and security leaks)
# P1-3 Fix: Extended list to cover security-sensitive information
SENSITIVE_KEYWORDS = [
    # Game spoiler keywords
    'role=',
    'werewolf votes',
    'verified',
    'teammate',
    'wolf_votes',
    'is_werewolf',
    'has_save_potion',
    'has_poison_potion',
    # Security-sensitive keywords
    'api_key',
    'api-key',
    'apikey',
    'secret',
    'password',
    'token',
    'authorization',
    'bearer',
    'credential',
    'private_key',
    'jwt_secret',
    'admin_key',
]


class GameLogHandler(logging.Handler):
    """Custom logging handler that captures game-related logs."""

    def emit(self, record):
        """Process a log record and store it if it's game-related."""
        try:
            # Extract game_id from record if available
            game_id = getattr(record, 'game_id', None)

            if game_id:
                # Ensure deque exists for this game
                if game_id not in game_logs:
                    game_logs[game_id] = deque(maxlen=500)  # Keep last 500 logs

                # Sanitize the log message
                sanitized = self._sanitize(record)
                if sanitized:
                    game_logs[game_id].append(sanitized)
        except Exception:
            # Don't let logging errors break the game
            pass

    def _sanitize(self, record) -> Optional[Dict]:
        """Remove sensitive information from log message."""
        msg = record.getMessage()

        # Filter out messages containing sensitive keywords
        msg_lower = msg.lower()
        if any(keyword in msg_lower for keyword in SENSITIVE_KEYWORDS):
            return None

        # Also filter DEBUG level logs (too verbose)
        if record.levelno < logging.INFO:
            return None

        return {
            "timestamp": record.created,
            "level": record.levelname,
            "message": msg,
            "module": record.module,
        }


def get_game_logs(game_id: str, limit: int = 100) -> List[Dict]:
    """
    Get sanitized logs for a specific game.

    Args:
        game_id: The game ID
        limit: Maximum number of logs to return (default: 100)

    Returns:
        List of log entries (most recent first)
    """
    if game_id not in game_logs:
        return []

    logs = list(game_logs[game_id])

    # Return most recent logs first
    logs.reverse()

    return logs[:limit]


def clear_game_logs(game_id: str):
    """Clear logs for a specific game."""
    if game_id in game_logs:
        del game_logs[game_id]


def init_game_logging():
    """Initialize game logging handler."""
    handler = GameLogHandler()
    handler.setLevel(logging.INFO)

    # Add to game_engine logger
    game_logger = logging.getLogger('app.services.game_engine')
    game_logger.addHandler(handler)

    # Add to llm logger
    llm_logger = logging.getLogger('app.services.llm')
    llm_logger.addHandler(handler)

    return handler
