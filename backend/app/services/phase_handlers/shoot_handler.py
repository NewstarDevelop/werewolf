"""Shoot phase handlers - death shoot (hunter/wolf king) and hunter shoot phases."""
import logging
import random
from typing import TYPE_CHECKING

from app.models.game import Game
from app.schemas.enums import (
    GamePhase, GameStatus, Role, ActionType, MessageType
)
from app.i18n import t

if TYPE_CHECKING:
    from app.services.llm import LLMService

logger = logging.getLogger(__name__)


async def handle_death_shoot(game: Game, llm: "LLMService") -> dict:
    """Handle death shoot phase (for hunter and wolf king)."""
    shooter = game.get_player(game.current_actor_seat) if game.current_actor_seat else None
    if not shooter:
        return continue_after_death_shoot(game)

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
        return continue_after_death_shoot(game)

    # Check if shooter is human player (multi-player support)
    # Priority: human_seats (room mode) > is_human (single-player mode)
    is_human_shooter = (
        (game.human_seats and shooter.seat_id in game.human_seats) or
        (not game.human_seats and shooter.is_human)
    )
    if is_human_shooter:
        return {"status": "waiting_for_human", "phase": game.phase}

    # AI shooter decides
    targets = [p.seat_id for p in game.get_alive_players()]
    if targets:
        target = await llm.decide_shoot_target(shooter, game, targets)
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
    return continue_after_death_shoot(game)


def continue_after_death_shoot(game: Game) -> dict:
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


async def handle_hunter_shoot(game: Game, llm: "LLMService") -> dict:
    """Handle hunter shooting."""
    hunter = game.get_player(game.current_actor_seat) if game.current_actor_seat else None
    if not hunter or hunter.role != Role.HUNTER:
        # Skip if not hunter
        return continue_after_hunter(game)

    if not hunter.can_shoot:
        seat_suffix = "号" if game.language == "zh" else ""
        game.add_message(0, t("system_messages.hunter_poisoned", language=game.language, seat_id=f"{hunter.seat_id}{seat_suffix}"), MessageType.SYSTEM)
        return continue_after_hunter(game)

    # Check if hunter is human player (multi-player support)
    # Priority: human_seats (room mode) > is_human (single-player mode)
    is_human_hunter = (
        (game.human_seats and hunter.seat_id in game.human_seats) or
        (not game.human_seats and hunter.is_human)
    )
    if is_human_hunter:
        return {"status": "waiting_for_human", "phase": game.phase}

    # AI hunter decides
    targets = [p.seat_id for p in game.get_alive_players()]
    if targets:
        target = await llm.decide_shoot_target(hunter, game, targets)
        if target:
            seat_suffix = "号" if game.language == "zh" else ""
            game.add_message(0, t("system_messages.hunter_shot", language=game.language, hunter_id=f"{hunter.seat_id}{seat_suffix}", target_id=f"{target}{seat_suffix}"), MessageType.SYSTEM)
            game.kill_player(target)
            game.add_action(hunter.seat_id, ActionType.SHOOT, target)
        else:
            seat_suffix = "号" if game.language == "zh" else ""
            game.add_message(0, t("system_messages.hunter_abstain", language=game.language, seat_id=f"{hunter.seat_id}{seat_suffix}"), MessageType.SYSTEM)

    return continue_after_hunter(game)


def continue_after_hunter(game: Game) -> dict:
    """Continue game flow after hunter action."""
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
