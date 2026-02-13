"""Night phase handlers - werewolf chat, kill, guard, seer, witch phases."""
import logging
import re
import secrets
from typing import TYPE_CHECKING

from app.models.game import Game, WOLF_ROLES
from app.schemas.enums import (
    GamePhase, GameStatus, Role, ActionType, MessageType
)
from app.i18n import t

if TYPE_CHECKING:
    from app.services.llm import LLMService

logger = logging.getLogger(__name__)
_rng = secrets.SystemRandom()


async def handle_night_start(game: Game) -> dict:
    """Handle night start - transition to werewolf chat phase."""
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


async def handle_night_werewolf_chat(game: Game, llm: "LLMService") -> dict:
    """Handle werewolf chat phase - werewolves discuss before voting."""
    alive_wolves = game.get_alive_werewolves()

    # P0-HIGH-002: Check if any human wolves still need to chat
    human_wolves = [w for w in alive_wolves if game.is_human_player(w.seat_id)]
    if any(w.seat_id not in game.wolf_chat_completed for w in human_wolves):
        return {"status": "waiting_for_human", "phase": game.phase}

    # AI werewolves chat
    for wolf in alive_wolves:
        if not game.is_human_player(wolf.seat_id) and wolf.seat_id not in game.wolf_chat_completed:
            speech = await llm.generate_speech(wolf, game)
            game.add_message(wolf.seat_id, speech, MessageType.WOLF_CHAT)
            game.wolf_chat_completed.add(wolf.seat_id)

    # All werewolves have chatted, move to kill vote phase
    # Summarize wolf night plan before moving to next phase
    game.wolf_night_plan = summarize_wolf_plan(game)
    game.add_message(0, t("system_messages.werewolf_discussion_end", language=game.language), MessageType.SYSTEM)
    game.phase = GamePhase.NIGHT_WEREWOLF
    game.increment_version()
    return {"status": "updated", "new_phase": game.phase}


async def handle_night_werewolf(game: Game, llm: "LLMService") -> dict:
    """Handle werewolf kill phase."""
    alive_wolves = game.get_alive_werewolves()

    # P0-HIGH-002: Check if any human wolves still need to vote
    human_wolves = [w for w in alive_wolves if game.is_human_player(w.seat_id)]
    if any(w.seat_id not in game.wolf_votes for w in human_wolves):
        return {"status": "waiting_for_human", "phase": game.phase}

    # AI werewolves vote
    for wolf in alive_wolves:
        if not game.is_human_player(wolf.seat_id) and wolf.seat_id not in game.wolf_votes:
            # 狼人可以击杀任何存活玩家（包括队友，实现自刀策略）
            targets = [p.seat_id for p in game.get_alive_players()
                      if p.seat_id != wolf.seat_id]
            if targets:
                target = await llm.decide_kill_target(wolf, game, targets)
                game.wolf_votes[wolf.seat_id] = target
                game.add_action(wolf.seat_id, ActionType.KILL, target)

    # Check if white wolf king used self-destruct
    if game.white_wolf_king_explode_target:
        # White wolf king self-destruct replaces normal wolf kill
        # Add explode target to unblockable deaths (cannot be saved by guard/witch)
        game.pending_deaths_unblockable.append(game.white_wolf_king_explode_target)

        # 白狼王自爆后自己也死亡（无法被守卫/女巫阻挡）
        white_wolf_king = game.get_player_by_role(Role.WHITE_WOLF_KING)
        if white_wolf_king:
            game.pending_deaths_unblockable.append(white_wolf_king.seat_id)

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
            game.night_kill_target = _rng.choice(top_targets)
            game.pending_deaths.append(game.night_kill_target)

    game.phase = GamePhase.NIGHT_GUARD if game.get_player_by_role(Role.GUARD) else GamePhase.NIGHT_SEER
    game.increment_version()
    return {"status": "updated", "new_phase": game.phase}


async def handle_night_guard(game: Game, llm: "LLMService" = None) -> dict:
    """Handle guard protection phase."""
    guard = game.get_player_by_role(Role.GUARD)

    if guard and guard.is_alive:
        if game.is_human_player(guard.seat_id):
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
                if llm:
                    target = await llm.decide_guard_target(guard, game, protect_choices)
                else:
                    # Fallback to random if no LLM available
                    choice = _rng.choice(protect_choices + [0])
                    target = choice if choice != 0 else None
                game.guard_target = target
                if game.guard_target:
                    game.add_action(guard.seat_id, ActionType.PROTECT, game.guard_target)
            game.guard_decided = True

    game.phase = GamePhase.NIGHT_SEER
    game.increment_version()
    return {"status": "updated", "new_phase": game.phase}


async def handle_night_seer(game: Game, llm: "LLMService") -> dict:
    """Handle seer verification phase."""
    seer = game.get_player_by_role(Role.SEER)

    if seer and seer.is_alive:
        if game.is_human_player(seer.seat_id):
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
                target = await llm.decide_verify_target(seer, game, targets)
                target_player = game.get_player(target)
                if target_player:
                    is_wolf = target_player.role in WOLF_ROLES  # Includes wolf king and white wolf king
                    seer.verified_players[target] = is_wolf
                    game.add_action(seer.seat_id, ActionType.VERIFY, target)

    game.phase = GamePhase.NIGHT_WITCH
    game.increment_version()
    return {"status": "updated", "new_phase": game.phase}


async def handle_night_witch(game: Game, llm: "LLMService") -> dict:
    """Handle witch save/poison phase."""
    witch = game.get_player_by_role(Role.WITCH)

    if witch and witch.is_alive:
        if game.is_human_player(witch.seat_id):
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
            decision = await llm.decide_witch_action(witch, game)

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
            logger.info(t("log_messages.guard_witch_double_save", language=game.language, seat=game.night_kill_target))
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


def summarize_wolf_plan(game: Game) -> str:
    """Summarize wolf team's night discussion and strategy."""
    wolf_messages = [msg for msg in game.messages
                    if msg.msg_type == MessageType.WOLF_CHAT and msg.day == game.day]

    if not wolf_messages:
        return ""

    # Extract key strategy keywords
    keywords = {
        "zh": {
            "self_knife": ["自刀", "刀自己", "刀队友"],
            "claim_seer": ["跳预言家", "悍跳", "起跳"],
            "target": ["刀", "击杀", "杀"],
            "hide": ["深水", "隐藏", "低调"],
            "attack": ["冲锋", "带节奏", "攻击"]
        },
        "en": {
            "self_knife": ["self-knife", "knife teammate"],
            "claim_seer": ["claim seer", "counter-claim", "fake seer"],
            "target": ["kill", "target", "eliminate"],
            "hide": ["hide", "stay low", "deep wolf"],
            "attack": ["charge", "lead", "attack"]
        }
    }

    lang = "zh" if game.language == "zh" else "en"
    strategy_points = []

    # Analyze messages for strategy keywords
    for msg in wolf_messages:
        content = msg.content.lower()
        for strategy, patterns in keywords[lang].items():
            if any(pattern in content for pattern in patterns):
                if strategy == "self_knife":
                    strategy_points.append(t("wolf_strategy.self_knife", language=game.language))
                elif strategy == "claim_seer":
                    strategy_points.append(t("wolf_strategy.claim_seer", language=game.language))
                elif strategy == "target":
                    # Extract target number if mentioned
                    numbers = re.findall(r'(\d+)号', content) if lang == "zh" else re.findall(r'#(\d+)', content)
                    if numbers:
                        strategy_points.append(t("wolf_strategy.target", language=game.language, number=numbers[0]))

    # Remove duplicates and join
    strategy_points = list(dict.fromkeys(strategy_points))
    if strategy_points:
        return ", ".join(strategy_points[:3])  # Limit to 3 key points
    return ""
