"""Game engine - core game logic and state machine."""
import logging
import random
from typing import Optional

from app.models.game import Game, Player, game_store
from app.schemas.enums import (
    GamePhase, GameStatus, Role, ActionType, MessageType, Winner
)
from app.services.llm import LLMService, sanitize_text_input
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
            GamePhase.NIGHT_START: self._handle_night_start,
            GamePhase.NIGHT_WEREWOLF_CHAT: self._handle_night_werewolf_chat,
            GamePhase.NIGHT_WEREWOLF: self._handle_night_werewolf,
            GamePhase.NIGHT_GUARD: self._handle_night_guard,
            GamePhase.NIGHT_SEER: self._handle_night_seer,
            GamePhase.NIGHT_WITCH: self._handle_night_witch,
            GamePhase.DAY_ANNOUNCEMENT: self._handle_day_announcement,
            GamePhase.DAY_LAST_WORDS: self._handle_day_last_words,
            GamePhase.DAY_SPEECH: self._handle_day_speech,
            GamePhase.DAY_VOTE: self._handle_day_vote,
            GamePhase.DAY_VOTE_RESULT: self._handle_day_vote_result,
            GamePhase.HUNTER_SHOOT: self._handle_hunter_shoot,
            GamePhase.DEATH_SHOOT: self._handle_death_shoot,
            GamePhase.GAME_OVER: self._handle_game_over,
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

        allow_dead_hunter_shoot = (
            game.phase == GamePhase.HUNTER_SHOOT
            and player.role == Role.HUNTER
            and game.current_actor_seat == player.seat_id
            and player.can_shoot
            and action_type in (ActionType.SHOOT, ActionType.SKIP)
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

        # Night werewolf chat phase
        if phase == GamePhase.NIGHT_WEREWOLF_CHAT and player.role == Role.WEREWOLF:
            if action_type == ActionType.SPEAK and content:
                game.add_message(player.seat_id, content, MessageType.WOLF_CHAT)
                game.wolf_chat_completed.add(player.seat_id)
                game.add_action(player.seat_id, ActionType.SPEAK)
                return {"success": True, "message": t("api_responses.wolf_chat_sent", language=game.language)}

        # Night werewolf phase
        if phase == GamePhase.NIGHT_WEREWOLF and player.role == Role.WEREWOLF:
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

                # Validate target (cannot self-destruct self, that makes no sense)
                if target_id == player.seat_id:
                    return {"success": False, "message": "不能自爆自己"}

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
                    from app.models.game import WOLF_ROLES
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
                return {"success": True, "message": t("api_responses.hunter_shot_player", language=game.language, target_id=target_id), **self._continue_after_hunter(game)}

            if action_type == ActionType.SKIP:
                seat_suffix = "号" if game.language == "zh" else ""
                game.add_message(0, t("system_messages.hunter_abstain", language=game.language, seat_id=f"{player.seat_id}{seat_suffix}"), MessageType.SYSTEM)
                return {"success": True, "message": t("api_responses.hunter_abstain_shoot", language=game.language), **self._continue_after_hunter(game)}

        # Last words phase
        elif phase == GamePhase.DAY_LAST_WORDS:
            if action_type == ActionType.SPEAK and content:
                game.add_message(player.seat_id, content, MessageType.LAST_WORDS)
                return {"success": True, "message": t("api_responses.last_words_recorded", language=game.language)}

        return {"success": False, "message": t("api_responses.invalid_phase_action", language=game.language)}

    # ==================== Phase Handlers ====================

    async def _handle_night_start(self, game: Game) -> dict:
        """Handle night start - transition to werewolf chat phase (WL-010: async)."""
        game.add_message(0, t("system_messages.night_falls", language=game.language, day=game.day), MessageType.SYSTEM)
        game.phase = GamePhase.NIGHT_WEREWOLF_CHAT
        game.wolf_chat_completed = set()  # Reset wolf chat tracker
        game.wolf_votes = {}
        game.pending_deaths = []
        game.pending_deaths_unblockable = []  # Reset unblockable deaths
        game.white_wolf_king_explode_target = None  # Reset white wolf king explode target
        game.guard_target = None  # Reset guard target
        game.guard_decided = False  # Reset guard decision tracker
        game.seer_verified_this_night = False  # Reset seer verification tracker
        game.witch_save_decided = False
        game.witch_poison_decided = False
        game.increment_version()
        return {"status": "updated", "new_phase": game.phase}

    async def _handle_night_werewolf_chat(self, game: Game) -> dict:
        """Handle werewolf chat phase - werewolves discuss before voting (WL-010: async)."""
        alive_wolves = game.get_alive_werewolves()

        # P0-HIGH-002: 统一fallback逻辑 - human_seats (多人) > is_human (单人)
        human_wolves = [
            w for w in alive_wolves
            if (game.human_seats and w.seat_id in game.human_seats) or
               (not game.human_seats and w.is_human)
        ]
        if any(w.seat_id not in game.wolf_chat_completed for w in human_wolves):
            return {"status": "waiting_for_human", "phase": game.phase}

        # AI werewolves chat
        for wolf in alive_wolves:
            if not wolf.is_human and wolf.seat_id not in game.wolf_chat_completed:
                speech = await self.llm.generate_speech(wolf, game)  # WL-010: await
                game.add_message(wolf.seat_id, speech, MessageType.WOLF_CHAT)
                game.wolf_chat_completed.add(wolf.seat_id)

        # All werewolves have chatted, move to kill vote phase
        game.add_message(0, t("system_messages.werewolf_discussion_end", language=game.language), MessageType.SYSTEM)
        game.phase = GamePhase.NIGHT_WEREWOLF
        game.increment_version()
        return {"status": "updated", "new_phase": game.phase}

    async def _handle_night_werewolf(self, game: Game) -> dict:
        """Handle werewolf kill phase (WL-010: async)."""
        alive_wolves = game.get_alive_werewolves()

        # P0-HIGH-002: 统一fallback逻辑 - human_seats (多人) > is_human (单人)
        human_wolves = [
            w for w in alive_wolves
            if (game.human_seats and w.seat_id in game.human_seats) or
               (not game.human_seats and w.is_human)
        ]
        if any(w.seat_id not in game.wolf_votes for w in human_wolves):
            return {"status": "waiting_for_human", "phase": game.phase}

        # AI werewolves vote
        for wolf in alive_wolves:
            if not wolf.is_human and wolf.seat_id not in game.wolf_votes:
                # 狼人可以击杀任何存活玩家（包括队友，实现自刀策略）
                targets = [p.seat_id for p in game.get_alive_players()
                          if p.seat_id != wolf.seat_id]
                if targets:
                    target = await self.llm.decide_kill_target(wolf, game, targets)  # WL-010: await
                    game.wolf_votes[wolf.seat_id] = target
                    game.add_action(wolf.seat_id, ActionType.KILL, target)

        # Check if white wolf king used self-destruct
        if game.white_wolf_king_explode_target:
            # White wolf king self-destruct replaces normal wolf kill
            # Add explode target to unblockable deaths (cannot be saved by guard/witch)
            game.pending_deaths_unblockable.append(game.white_wolf_king_explode_target)
            # No night_kill_target (self-destruct replaces wolf kill)
            game.night_kill_target = None
        else:
            # Determine kill target (majority or random from votes)
            # Filter out white wolf king's special vote marker (-1)
            valid_votes = {seat: target for seat, target in game.wolf_votes.items() if target > 0}
            if valid_votes:
                vote_counts: dict[int, int] = {}
                for target in valid_votes.values():
                    vote_counts[target] = vote_counts.get(target, 0) + 1
                max_votes = max(vote_counts.values())
                top_targets = [t for t, v in vote_counts.items() if v == max_votes]
                game.night_kill_target = random.choice(top_targets)
                game.pending_deaths.append(game.night_kill_target)

        game.phase = GamePhase.NIGHT_GUARD if game.get_player_by_role(Role.GUARD) else GamePhase.NIGHT_SEER
        game.increment_version()
        return {"status": "updated", "new_phase": game.phase}

    async def _handle_night_guard(self, game: Game) -> dict:
        """Handle guard protection phase."""
        guard = game.get_player_by_role(Role.GUARD)

        if guard and guard.is_alive:
            if guard.is_human:
                # Human guard hasn't made decision yet
                if not game.guard_decided:
                    return {"status": "waiting_for_human", "phase": game.phase}
            else:
                # AI guard chooses protection target
                protect_choices = [p.seat_id for p in game.get_alive_players()]
                # Cannot guard same person consecutively
                if game.guard_last_target and game.guard_last_target in protect_choices:
                    protect_choices.remove(game.guard_last_target)

                if protect_choices:
                    # TODO: Implement AI guard decision via LLM
                    # For now, random choice or skip
                    target = random.choice(protect_choices + [0])  # 0 = skip
                    game.guard_target = target if target != 0 else None
                    if game.guard_target:
                        game.add_action(guard.seat_id, ActionType.PROTECT, game.guard_target)
                game.guard_decided = True

        game.phase = GamePhase.NIGHT_SEER
        game.increment_version()
        return {"status": "updated", "new_phase": game.phase}

    async def _handle_night_seer(self, game: Game) -> dict:
        """Handle seer verification phase (WL-010: async)."""
        seer = game.get_player_by_role(Role.SEER)

        if seer and seer.is_alive:
            if seer.is_human:
                # If human has already verified (or cannot verify anyone), move on.
                if game.seer_verified_this_night:
                    game.phase = GamePhase.NIGHT_WITCH
                    game.increment_version()
                    return {"status": "updated", "new_phase": game.phase}

                targets = [
                    p.seat_id
                    for p in game.get_alive_players()
                    if p.seat_id != seer.seat_id and p.seat_id not in seer.verified_players
                ]
                if not targets:
                    game.phase = GamePhase.NIGHT_WITCH
                    game.increment_version()
                    return {"status": "updated", "new_phase": game.phase}

                return {"status": "waiting_for_human", "phase": game.phase}
            else:
                # AI seer picks a target to verify
                targets = [p.seat_id for p in game.get_alive_players()
                          if p.seat_id != seer.seat_id
                          and p.seat_id not in seer.verified_players]
                if targets:
                    target = await self.llm.decide_verify_target(seer, game, targets)  # WL-010: await
                    target_player = game.get_player(target)
                    if target_player:
                        from app.models.game import WOLF_ROLES
                        is_wolf = target_player.role in WOLF_ROLES  # Includes wolf king and white wolf king
                        seer.verified_players[target] = is_wolf
                        game.add_action(seer.seat_id, ActionType.VERIFY, target)

        game.phase = GamePhase.NIGHT_WITCH
        game.increment_version()
        return {"status": "updated", "new_phase": game.phase}

    async def _handle_night_witch(self, game: Game) -> dict:
        """Handle witch save/poison phase (WL-010: async)."""
        witch = game.get_player_by_role(Role.WITCH)

        if witch and witch.is_alive:
            if witch.is_human:
                used_save_this_night = any(
                    a.day == game.day
                    and a.player_id == witch.seat_id
                    and a.action_type == ActionType.SAVE
                    for a in game.actions
                )

                # Phase 1: Save decision
                if not game.witch_save_decided:
                    can_save = bool(witch.has_save_potion and game.night_kill_target)
                    if can_save:
                        # Wait for human witch to decide on save potion
                        return {"status": "waiting_for_human", "phase": game.phase}

                    # Auto-skip save if no potion or no kill target
                    game.witch_save_decided = True
                    logger.info(f"Witch save phase auto-skipped (has_potion={witch.has_save_potion}, kill_target={game.night_kill_target})")

                # If used save this night, auto-skip poison (game rule)
                if used_save_this_night:
                    game.witch_poison_decided = True
                    logger.info("Witch poison phase auto-skipped (used save this night)")

                # Phase 2: Poison decision
                if not game.witch_poison_decided:
                    # If no poison potion, auto-skip poison
                    if not witch.has_poison_potion:
                        game.witch_poison_decided = True
                        logger.info("Witch poison phase auto-skipped (no poison potion)")
                    else:
                        # Wait for human witch to decide on poison potion
                        return {"status": "waiting_for_human", "phase": game.phase}

                # Both decisions complete, move to next phase
                logger.info("Witch phase complete")
            else:
                # AI witch decision
                decision = await self.llm.decide_witch_action(witch, game)  # WL-010: await

                if decision.get("save") and witch.has_save_potion:
                    if game.night_kill_target in game.pending_deaths:
                        witch.has_save_potion = False
                        game.pending_deaths.remove(game.night_kill_target)
                        game.add_action(witch.seat_id, ActionType.SAVE, game.night_kill_target)

                if decision.get("poison_target") and witch.has_poison_potion:
                    target = decision["poison_target"]
                    witch.has_poison_potion = False
                    game.pending_deaths.append(target)
                    game.add_action(witch.seat_id, ActionType.POISON, target)

                game.witch_save_decided = True
                game.witch_poison_decided = True

        # Process deaths
        # Check for "同守同救" rule: if both witch saved and guard protected the same target, that target dies
        witch_saved_target = None
        for action in game.actions:
            if action.day == game.day and action.action_type == ActionType.SAVE:
                witch_saved_target = action.target_id
                break

        # Apply guard protection (blocks wolf kill only, not poison or white wolf king explode)
        if game.guard_target and game.guard_target == game.night_kill_target:
            # Check for 同守同救 (both witch and guard saved the same person)
            if witch_saved_target == game.night_kill_target:
                # 同守同救: the target dies despite both protections
                # Add the target back to pending_deaths if it was removed by witch
                if game.night_kill_target not in game.pending_deaths:
                    game.pending_deaths.append(game.night_kill_target)
                logger.info(f"同守同救: {game.night_kill_target}号玩家因同时被守卫守护和女巫救治而死亡")
            else:
                # Normal guard protection (no witch save)
                if game.night_kill_target in game.pending_deaths:
                    game.pending_deaths.remove(game.night_kill_target)

        # Update guard's last target for next night's consecutive guard rule
        game.guard_last_target = game.guard_target

        # Calculate final deaths for this night
        # Merge blockable deaths (pending_deaths) and unblockable deaths (pending_deaths_unblockable)
        all_deaths = list(set(game.pending_deaths + game.pending_deaths_unblockable))
        game.last_night_deaths = all_deaths
        for seat_id in game.last_night_deaths:
            # Check if poisoned (for hunter)
            was_poisoned = any(
                a.action_type == ActionType.POISON and a.target_id == seat_id
                for a in game.actions if a.day == game.day
            )
            game.kill_player(seat_id, by_poison=was_poisoned)

        game.phase = GamePhase.DAY_ANNOUNCEMENT
        game.increment_version()
        return {"status": "updated", "new_phase": game.phase}

    async def _handle_day_announcement(self, game: Game) -> dict:
        """Announce night deaths and check for hunter trigger (WL-010: async)."""
        if game.last_night_deaths:
            separator = "、" if game.language == "zh" else ", "
            seat_suffix = "号" if game.language == "zh" else ""
            deaths_str = separator.join([f"{s}{seat_suffix}" for s in game.last_night_deaths])
            game.add_message(0, t("system_messages.day_breaks_deaths", language=game.language, deaths=deaths_str), MessageType.SYSTEM)

            # Check win condition immediately after night deaths (before hunter shoot)
            winner = game.check_winner()
            if winner:
                game.winner = winner
                game.status = GameStatus.FINISHED
                game.phase = GamePhase.GAME_OVER
                return {"status": "game_over", "winner": winner}

            # Check for hunter death
            for seat_id in game.last_night_deaths:
                player = game.get_player(seat_id)
                if player and player.role == Role.HUNTER and player.can_shoot:
                    game.current_actor_seat = seat_id
                    game.phase = GamePhase.HUNTER_SHOOT
                    return {"status": "updated", "new_phase": game.phase}
        else:
            game.add_message(0, t("system_messages.day_breaks_peaceful", language=game.language), MessageType.SYSTEM)

        # Check win condition (for peaceful nights)
        winner = game.check_winner()
        if winner:
            game.winner = winner
            game.status = GameStatus.FINISHED
            game.phase = GamePhase.GAME_OVER
            return {"status": "game_over", "winner": winner}

        # Setup speech order with random starting position
        # Rule: Each day, randomly select a starting seat from alive players
        # This ensures fairness and prevents position-based advantages
        alive_seats = game.get_alive_seats()
        start_seat = random.choice(alive_seats)
        start_idx = alive_seats.index(start_seat)
        game.speech_order = alive_seats[start_idx:] + alive_seats[:start_idx]
        game.current_speech_index = 0
        game.current_actor_seat = game.speech_order[0]

        game.phase = GamePhase.DAY_SPEECH
        game._spoken_seats_this_round.clear()  # P0 Fix: Reset speech tracker
        seat_suffix = "号" if game.language == "zh" else ""
        game.add_message(0, t("system_messages.speech_start", language=game.language, seat_id=f"{game.speech_order[0]}{seat_suffix}"), MessageType.SYSTEM)
        game.increment_version()
        return {"status": "updated", "new_phase": game.phase}

    async def _handle_day_last_words(self, game: Game) -> dict:
        """Handle last words for dead player (WL-010: async)."""
        # For simplicity, skip last words in MVP
        game.phase = GamePhase.DAY_SPEECH
        game._spoken_seats_this_round.clear()  # P0 Fix: Reset speech tracker
        game.increment_version()
        return {"status": "updated", "new_phase": game.phase}

    async def _handle_day_speech(self, game: Game) -> dict:
        """Handle day speech phase (WL-010: async)."""
        if game.current_speech_index >= len(game.speech_order):
            # All speeches done, move to vote
            game.phase = GamePhase.DAY_VOTE
            game.day_votes = {}
            game.add_message(0, t("system_messages.speech_end", language=game.language), MessageType.SYSTEM)
            game.increment_version()
            return {"status": "updated", "new_phase": game.phase}

        current_seat = game.speech_order[game.current_speech_index]
        game.current_actor_seat = current_seat
        player = game.get_player(current_seat)

        if not player:
            game.current_speech_index += 1
            return await self._handle_day_speech(game)  # WL-010: await recursive call

        if player.is_human:
            return {"status": "waiting_for_human", "phase": game.phase}

        # AI speech
        speech = await self.llm.generate_speech(player, game)  # WL-010: await
        game.add_message(player.seat_id, speech, MessageType.SPEECH)
        game.current_speech_index += 1

        # Update current_actor_seat to next speaker (fix for state management bug)
        if game.current_speech_index < len(game.speech_order):
            game.current_actor_seat = game.speech_order[game.current_speech_index]
        else:
            game.current_actor_seat = None

        game.increment_version()
        return {"status": "updated", "new_phase": game.phase}

    async def _handle_day_vote(self, game: Game) -> dict:
        """Handle day vote phase (WL-010: async)."""
        alive_players = game.get_alive_players()

        # P0-HIGH-002: 统一fallback逻辑 - human_seats (多人) > is_human (单人)
        human_alive_players = [
            p for p in alive_players
            if (game.human_seats and p.seat_id in game.human_seats) or
               (not game.human_seats and p.is_human)
        ]
        if any(p.seat_id not in game.day_votes for p in human_alive_players):
            return {"status": "waiting_for_human", "phase": game.phase}

        # AI players vote
        for player in alive_players:
            if not player.is_human and player.seat_id not in game.day_votes:
                targets = [p.seat_id for p in alive_players if p.seat_id != player.seat_id]
                # 获取完整的 LLM 响应（包含投票思考）
                response = await self.llm.generate_response(player, game, "vote", targets + [0])  # WL-010: await
                target = response.action_target if response.action_target is not None else targets[0] if targets else 0

                # 记录投票思考为 VOTE_THOUGHT（不让其他AI看到）
                if response.thought:
                    game.add_message(player.seat_id, response.thought, MessageType.VOTE_THOUGHT)

                game.day_votes[player.seat_id] = target
                game.add_action(player.seat_id, ActionType.VOTE, target)

        game.phase = GamePhase.DAY_VOTE_RESULT
        game.increment_version()
        return {"status": "updated", "new_phase": game.phase}

    async def _handle_day_vote_result(self, game: Game) -> dict:
        """Process vote results (WL-010: async)."""
        vote_counts: dict[int, int] = {}
        for target in game.day_votes.values():
            if target and target > 0:
                vote_counts[target] = vote_counts.get(target, 0) + 1

        # Announce votes
        vote_summary = []
        seat_suffix = "号" if game.language == "zh" else ""
        separator = "，" if game.language == "zh" else ", "
        vote_word = "投" if game.language == "zh" else " voted for "
        abstain_word = "弃票" if game.language == "zh" else " abstained"
        for voter, target in game.day_votes.items():
            if target and target > 0:
                vote_summary.append(f"{voter}{seat_suffix}{vote_word}{target}{seat_suffix}")
            else:
                vote_summary.append(f"{voter}{seat_suffix}{abstain_word}")
        game.add_message(0, t("system_messages.vote_result", language=game.language, summary=separator.join(vote_summary)), MessageType.SYSTEM)

        if not vote_counts:
            game.add_message(0, t("system_messages.vote_all_abstain", language=game.language), MessageType.SYSTEM)
        else:
            max_votes = max(vote_counts.values())
            top_targets = [t for t, v in vote_counts.items() if v == max_votes]

            if len(top_targets) > 1:
                # Tie - no one dies (simplified rule)
                game.add_message(0, t("system_messages.vote_tie", language=game.language), MessageType.SYSTEM)
            else:
                eliminated = top_targets[0]
                seat_suffix = "号" if game.language == "zh" else ""
                game.add_message(0, t("system_messages.player_exiled", language=game.language, seat_id=f"{eliminated}{seat_suffix}"), MessageType.SYSTEM)
                game.kill_player(eliminated)

                # Check win condition immediately after death (before hunter/wolf king shoot)
                winner = game.check_winner()
                if winner:
                    game.winner = winner
                    game.status = GameStatus.FINISHED
                    game.phase = GamePhase.GAME_OVER
                    return {"status": "game_over", "winner": winner}

                # Check for hunter or wolf king death shoot
                player = game.get_player(eliminated)
                if player:
                    # Hunter can shoot if not poisoned
                    if player.role == Role.HUNTER and player.can_shoot:
                        game.current_actor_seat = eliminated
                        game.phase = GamePhase.DEATH_SHOOT
                        return {"status": "updated", "new_phase": game.phase}
                    # Wolf king can shoot when voted out (only during day, not when poisoned)
                    elif player.role == Role.WOLF_KING:
                        game.current_actor_seat = eliminated
                        game.phase = GamePhase.DEATH_SHOOT
                        return {"status": "updated", "new_phase": game.phase}

        # Check win condition (for cases where no one was eliminated)
        winner = game.check_winner()
        if winner:
            game.winner = winner
            game.status = GameStatus.FINISHED
            game.phase = GamePhase.GAME_OVER
            return {"status": "game_over", "winner": winner}

        # Next night
        game.day += 1
        game.phase = GamePhase.NIGHT_START
        game.increment_version()
        return {"status": "updated", "new_phase": game.phase}

    async def _handle_death_shoot(self, game: Game) -> dict:
        """Handle death shoot phase (for hunter and wolf king)."""
        shooter = game.get_player(game.current_actor_seat)
        if not shooter:
            return self._continue_after_death_shoot(game)

        # Determine shooter type and eligibility
        can_shoot = False
        shooter_name = ""
        if shooter.role == Role.HUNTER:
            can_shoot = shooter.can_shoot  # Hunter can't shoot if poisoned
            shooter_name = "猎人" if game.language == "zh" else "Hunter"
        elif shooter.role == Role.WOLF_KING:
            can_shoot = True  # Wolf king can always shoot when voted out
            shooter_name = "狼王" if game.language == "zh" else "Wolf King"

        if not can_shoot:
            seat_suffix = "号" if game.language == "zh" else ""
            if shooter.role == Role.HUNTER:
                game.add_message(0, t("system_messages.hunter_poisoned", language=game.language, seat_id=f"{shooter.seat_id}{seat_suffix}"), MessageType.SYSTEM)
            return self._continue_after_death_shoot(game)

        if shooter.is_human:
            return {"status": "waiting_for_human", "phase": game.phase}

        # AI shooter decides
        targets = [p.seat_id for p in game.get_alive_players()]
        if targets:
            target = await self.llm.decide_shoot_target(shooter, game, targets)
            if target:
                seat_suffix = "号" if game.language == "zh" else ""
                shoot_message = f"{shooter_name}{shooter.seat_id}{seat_suffix}开枪带走了{target}{seat_suffix}"
                game.add_message(0, shoot_message, MessageType.SYSTEM)
                game.kill_player(target)
                game.add_action(shooter.seat_id, ActionType.SHOOT, target)
            else:
                seat_suffix = "号" if game.language == "zh" else ""
                abstain_message = f"{shooter_name}{shooter.seat_id}{seat_suffix}放弃开枪"
                game.add_message(0, abstain_message, MessageType.SYSTEM)

        game.increment_version()
        return self._continue_after_death_shoot(game)

    def _continue_after_death_shoot(self, game: Game) -> dict:
        """Continue game flow after death shoot action."""
        # Check win condition
        winner = game.check_winner()
        if winner:
            game.winner = winner
            game.status = GameStatus.FINISHED
            game.phase = GamePhase.GAME_OVER
            return {"status": "game_over", "winner": winner}

        # Determine next phase based on when shooter died
        if game.phase == GamePhase.DEATH_SHOOT:
            if game.current_actor_seat is None:
                logger.warning("DEATH_SHOOT phase but current_actor_seat is None, skipping to next phase")
                game.day += 1
                game.phase = GamePhase.NIGHT_START
                return {"status": "updated", "new_phase": game.phase}

            # Check if shooter died during night or day
            died_at_night = game.current_actor_seat in game.last_night_deaths

            if died_at_night:
                # Died at night - continue to day speech phase
                alive_seats = game.get_alive_seats()
                if alive_seats:
                    start_seat = random.choice(alive_seats)
                    start_idx = alive_seats.index(start_seat)
                    game.speech_order = alive_seats[start_idx:] + alive_seats[:start_idx]
                    game.current_speech_index = 0
                    game.current_actor_seat = game.speech_order[0]
                    game.phase = GamePhase.DAY_SPEECH
                    game._spoken_seats_this_round.clear()
                    seat_suffix = "号" if game.language == "zh" else ""
                    game.add_message(0, t("system_messages.speech_start", language=game.language, seat_id=f"{game.speech_order[0]}{seat_suffix}"), MessageType.SYSTEM)
            else:
                # Died during day vote - go to next night
                game.day += 1
                game.phase = GamePhase.NIGHT_START

        game.increment_version()
        return {"status": "updated", "new_phase": game.phase}

    async def _handle_hunter_shoot(self, game: Game) -> dict:
        """Handle hunter shooting (WL-010: async)."""
        hunter = game.get_player(game.current_actor_seat)
        if not hunter or hunter.role != Role.HUNTER:
            # Skip if not hunter
            return self._continue_after_hunter(game)  # P0-CRIT-001: sync call

        if not hunter.can_shoot:
            seat_suffix = "号" if game.language == "zh" else ""
            game.add_message(0, t("system_messages.hunter_poisoned", language=game.language, seat_id=f"{hunter.seat_id}{seat_suffix}"), MessageType.SYSTEM)
            return self._continue_after_hunter(game)  # P0-CRIT-001: sync call

        if hunter.is_human:
            return {"status": "waiting_for_human", "phase": game.phase}

        # AI hunter decides
        targets = [p.seat_id for p in game.get_alive_players()]
        if targets:
            target = await self.llm.decide_shoot_target(hunter, game, targets)  # WL-010: await
            if target:
                seat_suffix = "号" if game.language == "zh" else ""
                game.add_message(0, t("system_messages.hunter_shot", language=game.language, hunter_id=f"{hunter.seat_id}{seat_suffix}", target_id=f"{target}{seat_suffix}"), MessageType.SYSTEM)
                game.kill_player(target)
                game.add_action(hunter.seat_id, ActionType.SHOOT, target)
            else:
                seat_suffix = "号" if game.language == "zh" else ""
                game.add_message(0, t("system_messages.hunter_abstain", language=game.language, seat_id=f"{hunter.seat_id}{seat_suffix}"), MessageType.SYSTEM)

        return self._continue_after_hunter(game)  # P0-CRIT-001: sync call

    def _continue_after_hunter(self, game: Game) -> dict:
        """Continue game flow after hunter action (P0-CRIT-001: converted to sync)."""
        # Check win condition
        winner = game.check_winner()
        if winner:
            game.winner = winner
            game.status = GameStatus.FINISHED
            game.phase = GamePhase.GAME_OVER
            return {"status": "game_over", "winner": winner}

        # Determine next phase based on when hunter died
        if game.phase == GamePhase.HUNTER_SHOOT:
            # Validate current_actor_seat is set and valid
            if game.current_actor_seat is None:
                logger.warning("HUNTER_SHOOT phase but current_actor_seat is None, skipping to next phase")
                game.day += 1
                game.phase = GamePhase.NIGHT_START
                return {"status": "updated", "new_phase": game.phase}

            # Check if hunter died during night (hunter should be in last_night_deaths list)
            # vs during day vote (hunter not in last_night_deaths)
            hunter_died_at_night = game.current_actor_seat in game.last_night_deaths

            if hunter_died_at_night:
                # Hunter died at night - continue to day speech phase
                alive_seats = game.get_alive_seats()
                if alive_seats:
                    start_seat = random.choice(alive_seats)
                    start_idx = alive_seats.index(start_seat)
                    game.speech_order = alive_seats[start_idx:] + alive_seats[:start_idx]
                    game.current_speech_index = 0
                    game.current_actor_seat = game.speech_order[0]
                    game.phase = GamePhase.DAY_SPEECH
                    game._spoken_seats_this_round.clear()  # P0 Fix: Reset speech tracker
                    seat_suffix = "号" if game.language == "zh" else ""
                    game.add_message(0, t("system_messages.speech_start", language=game.language, seat_id=f"{game.speech_order[0]}{seat_suffix}"), MessageType.SYSTEM)
            else:
                # Hunter died during day vote - go to next night
                game.day += 1
                game.phase = GamePhase.NIGHT_START

        game.increment_version()
        return {"status": "updated", "new_phase": game.phase}

    async def _handle_game_over(self, game: Game) -> dict:
        """Handle game over (WL-010: async)."""
        winner_text = t("winners.villagers", language=game.language) if game.winner == Winner.VILLAGER else t("winners.werewolves", language=game.language)
        game.add_message(0, t("system_messages.game_over", language=game.language, winner=winner_text), MessageType.SYSTEM)
        game.increment_version()
        return {"status": "game_over", "winner": game.winner}


# Global engine instance
game_engine = GameEngine()
