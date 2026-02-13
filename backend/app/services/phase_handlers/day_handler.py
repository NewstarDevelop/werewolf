"""Day phase handlers - announcement, speech, vote, vote result phases."""
import logging
import secrets
from typing import TYPE_CHECKING

from app.models.game import Game
from app.schemas.enums import (
    GamePhase, GameStatus, Role, ActionType, MessageType, Winner
)
from app.i18n import t

if TYPE_CHECKING:
    from app.services.llm import LLMService

logger = logging.getLogger(__name__)
_rng = secrets.SystemRandom()


async def handle_day_announcement(game: Game) -> dict:
    """Announce night deaths and check for hunter trigger."""
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
    start_seat = _rng.choice(alive_seats)
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


async def handle_day_last_words(game: Game) -> dict:
    """Handle last words for dead player."""
    # For simplicity, skip last words in MVP
    game.phase = GamePhase.DAY_SPEECH
    game._spoken_seats_this_round.clear()  # P0 Fix: Reset speech tracker
    game.increment_version()
    return {"status": "updated", "new_phase": game.phase}


async def handle_day_speech(game: Game, llm: "LLMService") -> dict:
    """Handle day speech phase."""
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
        return await handle_day_speech(game, llm)  # Recursive call

    if game.is_human_player(player.seat_id):
        return {"status": "waiting_for_human", "phase": game.phase}

    # AI speech
    speech = await llm.generate_speech(player, game)
    game.add_message(player.seat_id, speech, MessageType.SPEECH)
    game.current_speech_index += 1

    # Update current_actor_seat to next speaker (fix for state management bug)
    if game.current_speech_index < len(game.speech_order):
        game.current_actor_seat = game.speech_order[game.current_speech_index]
    else:
        game.current_actor_seat = None

    game.increment_version()
    return {"status": "updated", "new_phase": game.phase}


async def handle_day_vote(game: Game, llm: "LLMService") -> dict:
    """Handle day vote phase."""
    alive_players = game.get_alive_players()

    human_alive_players = [p for p in alive_players if game.is_human_player(p.seat_id)]
    if any(p.seat_id not in game.day_votes for p in human_alive_players):
        return {"status": "waiting_for_human", "phase": game.phase}

    # AI players vote
    for player in alive_players:
        if not game.is_human_player(player.seat_id) and player.seat_id not in game.day_votes:
            targets = [p.seat_id for p in alive_players if p.seat_id != player.seat_id]
            # 获取完整的 LLM 响应（包含投票思考）
            response = await llm.generate_response(player, game, "vote", targets + [0])
            target = response.action_target if response.action_target is not None else targets[0] if targets else 0

            # 记录投票思考为 VOTE_THOUGHT（不让其他AI看到）
            if response.thought:
                game.add_message(player.seat_id, response.thought, MessageType.VOTE_THOUGHT)

            game.day_votes[player.seat_id] = target
            game.add_action(player.seat_id, ActionType.VOTE, target)

    game.phase = GamePhase.DAY_VOTE_RESULT
    game.increment_version()
    return {"status": "updated", "new_phase": game.phase}


async def handle_day_vote_result(game: Game) -> dict:
    """Process vote results."""
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
        top_targets = [tid for tid, v in vote_counts.items() if v == max_votes]

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


async def handle_game_over(game: Game) -> dict:
    """Handle game over."""
    winner_text = t("winners.villagers", language=game.language) if game.winner == Winner.VILLAGER else t("winners.werewolves", language=game.language)
    game.add_message(0, t("system_messages.game_over", language=game.language, winner=winner_text), MessageType.SYSTEM)
    game.increment_version()
    return {"status": "game_over", "winner": game.winner}
