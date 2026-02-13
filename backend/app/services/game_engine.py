"""Game engine - core game logic and state machine.

Refactored: Action handlers extracted to action_handlers/ module for better maintainability.
"""
import logging
from typing import Optional

from app.models.game import Game, Player, game_store, WOLF_ROLES
from app.schemas.enums import (
    GamePhase, GameStatus, Role, ActionType
)
from app.services.llm import LLMService, sanitize_text_input
from app.services.phase_handlers import (
    # Night handlers
    handle_night_start,
    handle_night_werewolf_chat,
    handle_night_werewolf,
    handle_night_guard,
    handle_night_seer,
    handle_night_witch,
    # Day handlers
    handle_day_announcement,
    handle_day_last_words,
    handle_day_speech,
    handle_day_vote,
    handle_day_vote_result,
    handle_game_over,
    # Shoot handlers
    handle_death_shoot,
    handle_hunter_shoot,
)
from app.services.action_handlers import (
    handle_wolf_chat_action,
    handle_wolf_kill_action,
    handle_white_wolf_king_action,
    handle_guard_action,
    handle_seer_action,
    handle_witch_action,
    handle_speech_action,
    handle_vote_action,
    handle_last_words_action,
    handle_death_shoot_action,
    handle_hunter_shoot_action,
)
from app.i18n import t

logger = logging.getLogger(__name__)


class GameEngine:
    """Core game engine handling state transitions and AI turns."""

    def __init__(self):
        self.llm = LLMService()
        # Register per-game rate limiter cleanup hook so resources are freed
        # when games are deleted or expire from GameStore.
        game_store._cleanup_hooks.append(
            lambda game_id: self.llm._per_game_limiter.cleanup_game(game_id)
        )

    async def close(self) -> None:
        """
        A7-FIX: Close LLM service and release resources.

        This should be called during application shutdown.
        """
        if self.llm:
            await self.llm.close()

    async def step(self, game_id: str) -> dict:
        """
        Advance the game state by one step (WL-010: async).
        Returns status and any relevant info.
        """
        game = game_store.get_game(game_id)
        if not game:
            return {"status": "error", "message": "Game not found"}

        if game.status == GameStatus.FINISHED:
            return {"status": "game_over", "winner": game.winner}

        start_day = game.day
        start_phase = game.phase.value
        start_status = game.status.value

        logger.info(
            "Step start: day=%s phase=%s status=%s",
            start_day,
            start_phase,
            start_status,
            extra={"game_id": game.id},
        )

        # Route to appropriate phase handler
        phase_handlers = {
            GamePhase.NIGHT_START: lambda g: handle_night_start(g),
            GamePhase.NIGHT_WEREWOLF_CHAT: lambda g: handle_night_werewolf_chat(g, self.llm),
            GamePhase.NIGHT_WEREWOLF: lambda g: handle_night_werewolf(g, self.llm),
            GamePhase.NIGHT_GUARD: lambda g: handle_night_guard(g, self.llm),
            GamePhase.NIGHT_SEER: lambda g: handle_night_seer(g, self.llm),
            GamePhase.NIGHT_WITCH: lambda g: handle_night_witch(g, self.llm),
            GamePhase.DAY_ANNOUNCEMENT: lambda g: handle_day_announcement(g),
            GamePhase.DAY_LAST_WORDS: lambda g: handle_day_last_words(g, self.llm),
            GamePhase.DAY_SPEECH: lambda g: handle_day_speech(g, self.llm),
            GamePhase.DAY_VOTE: lambda g: handle_day_vote(g, self.llm),
            GamePhase.DAY_VOTE_RESULT: lambda g: handle_day_vote_result(g),
            GamePhase.HUNTER_SHOOT: lambda g: handle_hunter_shoot(g, self.llm),
            GamePhase.DEATH_SHOOT: lambda g: handle_death_shoot(g, self.llm),
            GamePhase.GAME_OVER: lambda g: handle_game_over(g),
        }

        handler = phase_handlers.get(game.phase)
        if handler:
            result = await handler(game)
            new_phase = result.get("new_phase")
            if hasattr(new_phase, "value"):
                new_phase_value = new_phase.value
            elif new_phase is None and hasattr(game.phase, "value"):
                new_phase_value = game.phase.value
            else:
                new_phase_value = new_phase
            logger.info(
                "Step end: status=%s new_phase=%s",
                result.get("status"),
                new_phase_value,
                extra={"game_id": game.id},
            )
            # Persist snapshot after phase transition, or clean up on game over
            if result.get("status") == "game_over":
                game_store._delete_snapshot(game_id)
            else:
                game_store.save_game_state(game_id)
            return result

        return {"status": "error", "message": f"Unknown phase: {game.phase}"}

    async def process_human_action(
        self,
        game_id: str,
        seat_id: int,
        action_type: ActionType,
        target_id: Optional[int] = None,
        content: Optional[str] = None
    ) -> dict:
        """Process an action from the human player (async for lock compatibility)."""
        game = game_store.get_game(game_id)
        if not game:
            return {"success": False, "message": "Game not found"}

        # WL-009: Sanitize user-provided content to prevent prompt injection
        if content:
            content = sanitize_text_input(content, max_length=500)

        player = game.get_player(seat_id)
        if not player:
            return {"success": False, "message": "Invalid player"}

        # T-STAB-001 Fix: Use human_seats for multi-player, fallback to is_human for single-player
        if not game.is_human_player(seat_id):
            return {"success": False, "message": "Invalid player"}

        # Allow dead Hunter or Wolf King to shoot in their respective phases
        allow_dead_hunter_shoot = (
            game.phase in (GamePhase.HUNTER_SHOOT, GamePhase.DEATH_SHOOT)
            and player.role in (Role.HUNTER, Role.WOLF_KING)
            and game.current_actor_seat == player.seat_id
            and action_type in (ActionType.SHOOT, ActionType.SKIP)
            and (player.role == Role.WOLF_KING or player.can_shoot)
        )
        if not player.is_alive and not allow_dead_hunter_shoot:
            return {"success": False, "message": "Player is dead"}

        logger.info(
            "Human action received: seat_id=%s action_type=%s",
            seat_id,
            action_type.value,
            extra={"game_id": game.id},
        )

        # Validate action based on current phase
        start_version = game.state_version
        result = self._validate_and_execute_action(
            game, player, action_type, target_id, content
        )
        if result.get("success") and game.state_version == start_version:
            game.increment_version()

        # Persist snapshot after human action
        if result.get("success"):
            game_store.save_game_state(game_id)

        return result

    def _validate_and_execute_action(
        self,
        game: Game,
        player: Player,
        action_type: ActionType,
        target_id: Optional[int],
        content: Optional[str]
    ) -> dict:
        """Validate and execute a player action.
        
        Delegates to specialized action handlers based on game phase.
        """
        phase = game.phase

        # Night werewolf chat phase
        if phase == GamePhase.NIGHT_WEREWOLF_CHAT and player.role in WOLF_ROLES:
            return handle_wolf_chat_action(game, player, action_type, content)

        # Night werewolf phase - Werewolf and Wolf King
        if phase == GamePhase.NIGHT_WEREWOLF and player.role in (Role.WEREWOLF, Role.WOLF_KING):
            return handle_wolf_kill_action(game, player, action_type, target_id)

        # Night werewolf phase - White Wolf King
        elif phase == GamePhase.NIGHT_WEREWOLF and player.role == Role.WHITE_WOLF_KING:
            return handle_white_wolf_king_action(game, player, action_type, target_id)

        # Night guard phase
        elif phase == GamePhase.NIGHT_GUARD and player.role == Role.GUARD:
            return handle_guard_action(game, player, action_type, target_id)

        # Night seer phase
        elif phase == GamePhase.NIGHT_SEER and player.role == Role.SEER:
            return handle_seer_action(game, player, action_type, target_id)

        # Night witch phase
        elif phase == GamePhase.NIGHT_WITCH and player.role == Role.WITCH:
            return handle_witch_action(game, player, action_type, target_id)

        # Day speech phase
        elif phase == GamePhase.DAY_SPEECH:
            return handle_speech_action(game, player, action_type, content)

        # Day vote phase
        elif phase == GamePhase.DAY_VOTE:
            return handle_vote_action(game, player, action_type, target_id)

        # Death shoot phase (hunter or wolf king)
        elif phase == GamePhase.DEATH_SHOOT:
            return handle_death_shoot_action(game, player, action_type, target_id)

        # Hunter shoot phase (legacy)
        elif phase == GamePhase.HUNTER_SHOOT and player.role == Role.HUNTER:
            return handle_hunter_shoot_action(game, player, action_type, target_id)

        # Last words phase
        elif phase == GamePhase.DAY_LAST_WORDS:
            return handle_last_words_action(game, player, action_type, content)

        return {"success": False, "message": t("api_responses.invalid_phase_action", language=game.language)}


# Global engine instance
game_engine = GameEngine()
