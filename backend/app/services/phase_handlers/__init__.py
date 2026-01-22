"""Phase handlers for game engine - modular phase processing."""
from app.services.phase_handlers.night_handler import (
    handle_night_start,
    handle_night_werewolf_chat,
    handle_night_werewolf,
    handle_night_guard,
    handle_night_seer,
    handle_night_witch,
    summarize_wolf_plan,
)
from app.services.phase_handlers.day_handler import (
    handle_day_announcement,
    handle_day_last_words,
    handle_day_speech,
    handle_day_vote,
    handle_day_vote_result,
    handle_game_over,
)
from app.services.phase_handlers.shoot_handler import (
    handle_death_shoot,
    handle_hunter_shoot,
    continue_after_death_shoot,
    continue_after_hunter,
)

__all__ = [
    # Night handlers
    "handle_night_start",
    "handle_night_werewolf_chat",
    "handle_night_werewolf",
    "handle_night_guard",
    "handle_night_seer",
    "handle_night_witch",
    "summarize_wolf_plan",
    # Day handlers
    "handle_day_announcement",
    "handle_day_last_words",
    "handle_day_speech",
    "handle_day_vote",
    "handle_day_vote_result",
    "handle_game_over",
    # Shoot handlers
    "handle_death_shoot",
    "handle_hunter_shoot",
    "continue_after_death_shoot",
    "continue_after_hunter",
]
