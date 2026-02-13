"""Day phase action handlers for human players."""
from typing import Optional
from app.models.game import Game, Player
from app.schemas.enums import ActionType, MessageType
from app.i18n import t
from .base import validate_target, ActionResult


def handle_speech_action(
    game: Game,
    player: Player,
    action_type: ActionType,
    content: Optional[str]
) -> dict:
    """Handle day speech action."""
    if action_type != ActionType.SPEAK or not content:
        return ActionResult.fail(
            t("api_responses.invalid_action_for_phase", language=game.language)
        ).to_dict()

    # P0 Security Fix: WL-004 - Validate speech turn
    if game.current_actor_seat != player.seat_id:
        return ActionResult.fail(
            t("api_responses.not_your_turn", language=game.language)
        ).to_dict()

    if player.seat_id in game._spoken_seats_this_round:
        return ActionResult.fail(
            t("api_responses.already_spoken", language=game.language)
        ).to_dict()

    # Mark as spoken
    game._spoken_seats_this_round.add(player.seat_id)

    game.add_message(player.seat_id, content, MessageType.SPEECH)
    game.add_action(player.seat_id, ActionType.SPEAK)

    # Move to next speaker
    game.current_speech_index += 1
    if game.current_speech_index < len(game.speech_order):
        game.current_actor_seat = game.speech_order[game.current_speech_index]
    else:
        game.current_actor_seat = None

    return ActionResult.ok(
        t("api_responses.speech_recorded", language=game.language)
    ).to_dict()


def handle_vote_action(
    game: Game,
    player: Player,
    action_type: ActionType,
    target_id: Optional[int]
) -> dict:
    """Handle day vote action."""
    if action_type == ActionType.VOTE:
        if target_id is not None and target_id != 0:
            try:
                validate_target(game, target_id, ActionType.VOTE, player.seat_id)
            except ValueError as e:
                return ActionResult.fail(str(e)).to_dict()
        game.day_votes[player.seat_id] = target_id if target_id else 0
        game.add_action(player.seat_id, ActionType.VOTE, target_id)
        return ActionResult.ok(
            t("api_responses.vote_recorded", language=game.language)
        ).to_dict()

    elif action_type == ActionType.SKIP:
        # Abstain: record as voting for 0
        game.day_votes[player.seat_id] = 0
        game.add_action(player.seat_id, ActionType.VOTE, 0)
        return ActionResult.ok(
            t("api_responses.vote_abstained", language=game.language)
        ).to_dict()

    return ActionResult.fail(
        t("api_responses.invalid_action_for_phase", language=game.language)
    ).to_dict()


def handle_last_words_action(
    game: Game,
    player: Player,
    action_type: ActionType,
    content: Optional[str]
) -> dict:
    """Handle last words action."""
    if action_type == ActionType.SPEAK and content:
        game.add_message(player.seat_id, content, MessageType.LAST_WORDS)
        return ActionResult.ok(
            t("api_responses.last_words_recorded", language=game.language)
        ).to_dict()

    return ActionResult.fail(
        t("api_responses.invalid_action_for_phase", language=game.language)
    ).to_dict()
