"""Game engine - core game logic and state machine."""
import logging
from typing import Optional

from app.models.game import Game, Player, game_store, WOLF_ROLES
from app.schemas.enums import (
    GamePhase, GameStatus, Role, ActionType, MessageType, Winner
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
    continue_after_death_shoot,
    continue_after_hunter,
)
from app.i18n import t

logger = logging.getLogger(__name__)


def validate_target(
    game: Game,
    target_id: int,
    action_type: ActionType,
    actor_seat: int,
    allow_abstain: bool = False
) -> None:
    """
    Validate action target legality (WL-006).

    Args:
        game: Current game instance
        target_id: Target seat ID
        action_type: Type of action being performed
        actor_seat: Seat ID of the actor
        allow_abstain: Whether 0 (abstain/skip) is allowed

    Raises:
        ValueError: If target is invalid
    """
    # Allow abstain/skip (target_id = 0) if permitted
    if target_id == 0:
        if allow_abstain:
            return
        raise ValueError("无效的目标：不能选择 0")

    # Check if target seat exists
    if target_id not in game.players:
        raise ValueError(f"无效的目标：{target_id} 号玩家不存在")

    target_player = game.get_player(target_id)
    if not target_player:
        raise ValueError(f"无效的目标：{target_id} 号玩家不存在")

    # Check if target is alive (required for most actions)
    if not target_player.is_alive:
        raise ValueError(f"无效的目标：{target_id} 号玩家已死亡")

    # Prevent self-targeting for certain actions
    # KILL: Werewolves CAN target themselves (self-knife strategy for identity play)
    # POISON: Cannot poison self
    # VOTE: Can vote for others, not self
    # SHOOT: Cannot shoot self
    # VERIFY: Cannot verify self (already checked in handler, but add here for completeness)
    # PROTECT: 12-player mode allows self-guard, so removed from this list
    no_self_target_actions = [
        ActionType.POISON,
        ActionType.VOTE,
        ActionType.SHOOT,
        ActionType.VERIFY
    ]

    if action_type in no_self_target_actions and target_id == actor_seat:
        action_names = {
            ActionType.KILL: "击杀",
            ActionType.POISON: "毒",
            ActionType.VOTE: "投票给",
            ActionType.SHOOT: "射击",
            ActionType.VERIFY: "验证"
        }
        action_name = action_names.get(action_type, "选择")
        raise ValueError(f"不能{action_name}自己")


class GameEngine:
    """Core game engine handling state transitions and AI turns."""

    def __init__(self):
        self.llm = LLMService()

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
        # Handlers that need llm are wrapped with lambda to pass llm
        phase_handlers = {
            GamePhase.NIGHT_START: lambda g: handle_night_start(g),
            GamePhase.NIGHT_WEREWOLF_CHAT: lambda g: handle_night_werewolf_chat(g, self.llm),
            GamePhase.NIGHT_WEREWOLF: lambda g: handle_night_werewolf(g, self.llm),
            GamePhase.NIGHT_GUARD: lambda g: handle_night_guard(g),
            GamePhase.NIGHT_SEER: lambda g: handle_night_seer(g, self.llm),
            GamePhase.NIGHT_WITCH: lambda g: handle_night_witch(g, self.llm),
            GamePhase.DAY_ANNOUNCEMENT: lambda g: handle_day_announcement(g),
            GamePhase.DAY_LAST_WORDS: lambda g: handle_day_last_words(g),
            GamePhase.DAY_SPEECH: lambda g: handle_day_speech(g, self.llm),
            GamePhase.DAY_VOTE: lambda g: handle_day_vote(g, self.llm),
            GamePhase.DAY_VOTE_RESULT: lambda g: handle_day_vote_result(g),
            GamePhase.HUNTER_SHOOT: lambda g: handle_hunter_shoot(g, self.llm),
            GamePhase.DEATH_SHOOT: lambda g: handle_death_shoot(g, self.llm),
            GamePhase.GAME_OVER: lambda g: handle_game_over(g),
        }

        handler = phase_handlers.get(game.phase)
        if handler:
            result = await handler(game)  # WL-010: await async handler
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
            return result

        return {"status": "error", "message": f"Unknown phase: {game.phase}"}

    def process_human_action(
        self,
        game_id: str,
        seat_id: int,
        action_type: ActionType,
        target_id: Optional[int] = None,
        content: Optional[str] = None
    ) -> dict:
        """Process an action from the human player."""
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
        # Priority: human_seats (room mode) > is_human (single-player mode)
        is_human_player = (
            (game.human_seats and seat_id in game.human_seats) or
            (not game.human_seats and player.is_human)
        )
        if not is_human_player:
            return {"success": False, "message": "Invalid player"}

        # Allow dead Hunter or Wolf King to shoot in their respective phases
        # Hunter: can shoot if not poisoned (can_shoot=True)
        # Wolf King: can always shoot when voted out during day
        allow_dead_hunter_shoot = (
            game.phase in (GamePhase.HUNTER_SHOOT, GamePhase.DEATH_SHOOT)
            and player.role in (Role.HUNTER, Role.WOLF_KING)
            and game.current_actor_seat == player.seat_id
            and action_type in (ActionType.SHOOT, ActionType.SKIP)
            and (player.role == Role.WOLF_KING or player.can_shoot)  # Wolf King always can, Hunter checks can_shoot
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

        return result

    def _validate_and_execute_action(
        self,
        game: Game,
        player: Player,
        action_type: ActionType,
        target_id: Optional[int],
        content: Optional[str]
    ) -> dict:
        """Validate and execute a player action."""
        phase = game.phase

        # Night werewolf chat phase - all wolf-aligned roles participate
        if phase == GamePhase.NIGHT_WEREWOLF_CHAT and player.role in WOLF_ROLES:
            if action_type == ActionType.SPEAK:
                if not content:
                    return {"success": False, "message": t("api_responses.message_empty", language=game.language)}
                game.add_message(player.seat_id, content, MessageType.WOLF_CHAT)
                game.wolf_chat_completed.add(player.seat_id)
                game.add_action(player.seat_id, ActionType.SPEAK)
                return {"success": True, "message": t("api_responses.wolf_chat_sent", language=game.language)}
            else:
                return {"success": False, "message": t("api_responses.invalid_action_for_phase", language=game.language)}

        # Night werewolf phase - Werewolf and Wolf King vote for kill
        if phase == GamePhase.NIGHT_WEREWOLF and player.role in (Role.WEREWOLF, Role.WOLF_KING):
            if action_type == ActionType.KILL and target_id:
                # P0-HIGH-003: 统一错误处理 - 捕获validate_target异常
                try:
                    validate_target(game, target_id, ActionType.KILL, player.seat_id)
                except ValueError as e:
                    return {"success": False, "message": str(e)}
                game.wolf_votes[player.seat_id] = target_id
                game.add_action(player.seat_id, ActionType.KILL, target_id)
                return {"success": True, "message": t("api_responses.vote_recorded", language=game.language)}

        # Night werewolf phase - White wolf king can self-destruct
        elif phase == GamePhase.NIGHT_WEREWOLF and player.role == Role.WHITE_WOLF_KING:
            # White wolf king can either KILL (vote for normal wolf kill) or SELF_DESTRUCT
            if action_type == ActionType.KILL and target_id:
                # Normal wolf kill vote
                try:
                    validate_target(game, target_id, ActionType.KILL, player.seat_id)
                except ValueError as e:
                    return {"success": False, "message": str(e)}
                game.wolf_votes[player.seat_id] = target_id
                game.add_action(player.seat_id, ActionType.KILL, target_id)
                return {"success": True, "message": t("api_responses.vote_recorded", language=game.language)}

            elif action_type == ActionType.SELF_DESTRUCT and target_id:
                # White wolf king self-destruct
                if game.white_wolf_king_used_explode:
                    return {"success": False, "message": "你已使用过自爆技能"}

                # Validate target (white wolf king self-destruct must target another player)
                if target_id == player.seat_id:
                    return {"success": False, "message": "白狼王自爆必须选择其他玩家作为目标"}

                try:
                    validate_target(game, target_id, ActionType.SELF_DESTRUCT, player.seat_id, allow_abstain=False)
                except ValueError as e:
                    return {"success": False, "message": str(e)}

                # Record self-destruct
                game.white_wolf_king_explode_target = target_id
                game.white_wolf_king_used_explode = True
                # White wolf king "votes" for self-destruct (to mark as voted)
                game.wolf_votes[player.seat_id] = -1  # Special marker: -1 means self-destruct
                game.add_action(player.seat_id, ActionType.SELF_DESTRUCT, target_id)
                return {"success": True, "message": f"白狼王自爆，带走{target_id}号玩家！今晚无狼刀。"}

        # Night guard phase
        elif phase == GamePhase.NIGHT_GUARD and player.role == Role.GUARD:
            if action_type == ActionType.PROTECT:
                # Guard can skip by choosing target_id = 0
                if target_id == 0:
                    game.guard_target = None
                    game.guard_decided = True
                    return {"success": True, "message": "已跳过守护"}

                # Validate target
                if target_id is not None:
                    try:
                        validate_target(game, target_id, ActionType.PROTECT, player.seat_id, allow_abstain=False)
                    except ValueError as e:
                        return {"success": False, "message": str(e)}

                    # Check consecutive guard rule
                    if target_id == game.guard_last_target:
                        return {"success": False, "message": "不能连续两夜守护同一人"}

                    game.guard_target = target_id
                    game.guard_decided = True
                    game.add_action(player.seat_id, ActionType.PROTECT, target_id)
                    return {"success": True, "message": f"已守护{target_id}号玩家"}

        # Night seer phase
        elif phase == GamePhase.NIGHT_SEER and player.role == Role.SEER:
            if action_type == ActionType.VERIFY and target_id:
                # Check if already verified someone this night
                if game.seer_verified_this_night:
                    return {"success": False, "message": t("api_responses.seer_already_verified", language=game.language)}

                # Check if trying to verify self
                if target_id == player.seat_id:
                    return {"success": False, "message": t("api_responses.cannot_verify_self", language=game.language)}

                target = game.get_player(target_id)
                if target:
                    is_wolf = target.role in WOLF_ROLES  # Includes wolf king and white wolf king
                    player.verified_players[target_id] = is_wolf
                    game.seer_verified_this_night = True  # Mark as verified
                    game.add_action(player.seat_id, ActionType.VERIFY, target_id)
                    result = t("prompts.seer_result_wolf", language=game.language) if is_wolf else t("prompts.seer_result_villager", language=game.language)
                    return {
                        "success": True,
                        "message": t("api_responses.seer_result", language=game.language, target_id=target_id, result=result)
                    }

        # Night witch phase
        elif phase == GamePhase.NIGHT_WITCH and player.role == Role.WITCH:
            used_save_this_night = any(
                a.day == game.day
                and a.player_id == player.seat_id
                and a.action_type == ActionType.SAVE
                for a in game.actions
            )

            if action_type == ActionType.SAVE:
                if game.witch_save_decided:
                    return {"success": False, "message": t("api_responses.witch_save_decided", language=game.language)}
                if player.has_save_potion and game.night_kill_target:
                    player.has_save_potion = False
                    if game.night_kill_target in game.pending_deaths:
                        game.pending_deaths.remove(game.night_kill_target)
                    game.add_action(player.seat_id, ActionType.SAVE, game.night_kill_target)
                    game.witch_save_decided = True
                    # 规则：同一晚使用了解药则不能再使用毒药
                    game.witch_poison_decided = True
                    return {"success": True, "message": t("api_responses.antidote_used", language=game.language)}
                return {"success": False, "message": t("api_responses.cannot_use_antidote", language=game.language)}
            elif action_type == ActionType.POISON and target_id:
                if not game.witch_save_decided:
                    return {"success": False, "message": t("api_responses.decide_save_first", language=game.language)}
                if game.witch_poison_decided:
                    return {"success": False, "message": t("api_responses.witch_poison_decided", language=game.language)}
                if used_save_this_night:
                    return {"success": False, "message": t("api_responses.save_used_cannot_poison", language=game.language)}
                if player.has_poison_potion:
                    # P0-HIGH-003: 统一错误处理 - 捕获validate_target异常
                    try:
                        validate_target(game, target_id, ActionType.POISON, player.seat_id)
                    except ValueError as e:
                        return {"success": False, "message": str(e)}
                    player.has_poison_potion = False
                    game.pending_deaths.append(target_id)
                    game.add_action(player.seat_id, ActionType.POISON, target_id)
                    game.witch_poison_decided = True
                    return {"success": True, "message": t("api_responses.poison_used", language=game.language)}
                return {"success": False, "message": t("api_responses.cannot_use_poison", language=game.language)}
            elif action_type == ActionType.SKIP:
                if not game.witch_save_decided:
                    game.witch_save_decided = True
                    return {"success": True, "message": t("api_responses.skip_antidote", language=game.language)}

                if not game.witch_poison_decided:
                    game.witch_poison_decided = True
                    return {"success": True, "message": t("api_responses.skip_poison", language=game.language)}

                return {"success": True, "message": t("api_responses.skip", language=game.language)}

        # Day speech phase
        elif phase == GamePhase.DAY_SPEECH:
            if action_type == ActionType.SPEAK and content:
                # P0 Security Fix: WL-004 - Validate speech turn
                # HIGH FIX: 统一错误处理，返回字典而非抛出异常
                if game.current_actor_seat != player.seat_id:
                    return {
                        "success": False,
                        "message": f"Not your turn to speak. Current speaker is seat {game.current_actor_seat}"
                    }
                if player.seat_id in game._spoken_seats_this_round:
                    return {"success": False, "message": "You have already spoken in this round"}

                # Mark as spoken
                game._spoken_seats_this_round.add(player.seat_id)

                game.add_message(player.seat_id, content, MessageType.SPEECH)
                game.add_action(player.seat_id, ActionType.SPEAK)
                # Move to next speaker
                game.current_speech_index += 1
                # Update current_actor_seat to next speaker
                if game.current_speech_index < len(game.speech_order):
                    game.current_actor_seat = game.speech_order[game.current_speech_index]
                else:
                    game.current_actor_seat = None
                return {"success": True, "message": t("api_responses.speech_recorded", language=game.language)}

        # Day vote phase
        elif phase == GamePhase.DAY_VOTE:
            if action_type == ActionType.VOTE:
                # P0-HIGH-003: 统一错误处理 - 捕获validate_target异常
                if target_id is not None and target_id != 0:
                    try:
                        validate_target(game, target_id, ActionType.VOTE, player.seat_id)
                    except ValueError as e:
                        return {"success": False, "message": str(e)}
                game.day_votes[player.seat_id] = target_id if target_id else 0
                game.add_action(player.seat_id, ActionType.VOTE, target_id)
                return {"success": True, "message": t("api_responses.vote_recorded", language=game.language)}
            elif action_type == ActionType.SKIP:
                # 弃票：记录为投票给 0
                game.day_votes[player.seat_id] = 0
                game.add_action(player.seat_id, ActionType.VOTE, 0)
                return {"success": True, "message": t("api_responses.vote_abstained", language=game.language)}

        # Death shoot phase (hunter or wolf king)
        elif phase == GamePhase.DEATH_SHOOT:
            if action_type == ActionType.SHOOT:
                # Only hunter or wolf king can shoot in this phase
                if player.role not in [Role.HUNTER, Role.WOLF_KING]:
                    return {"success": False, "message": "只有猎人或狼王可以在此阶段开枪"}

                # Skip shooting (target_id = 0)
                if target_id == 0:
                    seat_suffix = "号" if game.language == "zh" else ""
                    shooter_name = "猎人" if player.role == Role.HUNTER else "狼王"
                    abstain_message = f"{shooter_name}{player.seat_id}{seat_suffix}放弃开枪"
                    game.add_message(0, abstain_message, MessageType.SYSTEM)
                    return {"success": True, "message": "已放弃开枪"}

                # Validate target
                if target_id is not None:
                    try:
                        validate_target(game, target_id, ActionType.SHOOT, player.seat_id, allow_abstain=False)
                    except ValueError as e:
                        return {"success": False, "message": str(e)}

                    # Execute shoot
                    seat_suffix = "号" if game.language == "zh" else ""
                    shooter_name = "猎人" if player.role == Role.HUNTER else "狼王"
                    shoot_message = f"{shooter_name}{player.seat_id}{seat_suffix}开枪带走了{target_id}{seat_suffix}"
                    game.add_message(0, shoot_message, MessageType.SYSTEM)
                    game.kill_player(target_id)
                    game.add_action(player.seat_id, ActionType.SHOOT, target_id)
                    return {"success": True, "message": f"已射击{target_id}号玩家"}

        # Hunter shoot phase (legacy, backward compatibility)
        elif phase == GamePhase.HUNTER_SHOOT and player.role == Role.HUNTER:
            if game.current_actor_seat != player.seat_id:
                return {"success": False, "message": t("api_responses.not_your_turn", language=game.language)}

            if not player.can_shoot:
                return {"success": False, "message": t("api_responses.cannot_shoot", language=game.language)}

            if action_type == ActionType.SHOOT and target_id:
                # P0-HIGH-003: 统一错误处理 - 捕获validate_target异常
                try:
                    validate_target(game, target_id, ActionType.SHOOT, player.seat_id)
                except ValueError as e:
                    return {"success": False, "message": str(e)}
                seat_suffix = "号" if game.language == "zh" else ""
                game.add_message(0, t("system_messages.hunter_shot", language=game.language, hunter_id=f"{player.seat_id}{seat_suffix}", target_id=f"{target_id}{seat_suffix}"), MessageType.SYSTEM)
                game.kill_player(target_id)
                game.add_action(player.seat_id, ActionType.SHOOT, target_id)
                return {"success": True, "message": t("api_responses.hunter_shot_player", language=game.language, target_id=target_id), **continue_after_hunter(game)}

            if action_type == ActionType.SKIP:
                seat_suffix = "号" if game.language == "zh" else ""
                game.add_message(0, t("system_messages.hunter_abstain", language=game.language, seat_id=f"{player.seat_id}{seat_suffix}"), MessageType.SYSTEM)
                return {"success": True, "message": t("api_responses.hunter_abstain_shoot", language=game.language), **continue_after_hunter(game)}

        # Last words phase
        elif phase == GamePhase.DAY_LAST_WORDS:
            if action_type == ActionType.SPEAK and content:
                game.add_message(player.seat_id, content, MessageType.LAST_WORDS)
                return {"success": True, "message": t("api_responses.last_words_recorded", language=game.language)}

        return {"success": False, "message": t("api_responses.invalid_phase_action", language=game.language)}


# Global engine instance
game_engine = GameEngine()
