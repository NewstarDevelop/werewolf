"""Action handlers for human player actions.

This module exports all action handlers used by game_engine.py.
"""
from .night_actions import (
    handle_wolf_chat_action,
    handle_wolf_kill_action,
    handle_white_wolf_king_action,
    handle_guard_action,
    handle_seer_action,
    handle_witch_action,
)
from .day_actions import (
    handle_speech_action,
    handle_vote_action,
    handle_last_words_action,
)
from .shoot_actions import (
    handle_death_shoot_action,
    handle_hunter_shoot_action,
)
from .base import validate_target, ActionResult

__all__ = [
    # Night actions
    "handle_wolf_chat_action",
    "handle_wolf_kill_action",
    "handle_white_wolf_king_action",
    "handle_guard_action",
    "handle_seer_action",
    "handle_witch_action",
    # Day actions
    "handle_speech_action",
    "handle_vote_action",
    "handle_last_words_action",
    # Shoot actions
    "handle_death_shoot_action",
    "handle_hunter_shoot_action",
    # Base utilities
    "validate_target",
    "ActionResult",
]
