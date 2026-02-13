"""Night phase action handlers for human players."""
from typing import Optional
from app.models.game import Game, Player, WOLF_ROLES
from app.schemas.enums import ActionType, MessageType, Role
from app.i18n import t
from .base import validate_target, ActionResult


def handle_wolf_chat_action(
    game: Game,
    player: Player,
    action_type: ActionType,
    content: Optional[str]
) -> dict:
    """Handle wolf chat phase action."""
    if action_type == ActionType.SPEAK:
        if not content:
            return ActionResult.fail(
                t("api_responses.message_empty", language=game.language)
            ).to_dict()
        game.add_message(player.seat_id, content, MessageType.WOLF_CHAT)
        game.wolf_chat_completed.add(player.seat_id)
        game.add_action(player.seat_id, ActionType.SPEAK)
        return ActionResult.ok(
            t("api_responses.wolf_chat_sent", language=game.language)
        ).to_dict()
    return ActionResult.fail(
        t("api_responses.invalid_action_for_phase", language=game.language)
    ).to_dict()


def handle_wolf_kill_action(
    game: Game,
    player: Player,
    action_type: ActionType,
    target_id: Optional[int]
) -> dict:
    """Handle werewolf/wolf king kill vote action."""
    if action_type == ActionType.KILL and target_id:
        try:
            validate_target(game, target_id, ActionType.KILL, player.seat_id)
        except ValueError as e:
            return ActionResult.fail(str(e)).to_dict()
        game.wolf_votes[player.seat_id] = target_id
        game.add_action(player.seat_id, ActionType.KILL, target_id)
        return ActionResult.ok(
            t("api_responses.vote_recorded", language=game.language)
        ).to_dict()
    return ActionResult.fail(
        t("api_responses.invalid_action_for_phase", language=game.language)
    ).to_dict()


def handle_white_wolf_king_action(
    game: Game,
    player: Player,
    action_type: ActionType,
    target_id: Optional[int]
) -> dict:
    """Handle white wolf king actions (kill vote or self-destruct)."""
    if action_type == ActionType.KILL and target_id:
        try:
            validate_target(game, target_id, ActionType.KILL, player.seat_id)
        except ValueError as e:
            return ActionResult.fail(str(e)).to_dict()
        game.wolf_votes[player.seat_id] = target_id
        game.add_action(player.seat_id, ActionType.KILL, target_id)
        return ActionResult.ok(
            t("api_responses.vote_recorded", language=game.language)
        ).to_dict()

    elif action_type == ActionType.SELF_DESTRUCT and target_id:
        if game.white_wolf_king_used_explode:
            return ActionResult.fail(t("action_result.self_destruct_used", language=game.language)).to_dict()

        if target_id == player.seat_id:
            return ActionResult.fail(t("action_result.self_destruct_self", language=game.language)).to_dict()

        try:
            validate_target(game, target_id, ActionType.SELF_DESTRUCT, player.seat_id, allow_abstain=False)
        except ValueError as e:
            return ActionResult.fail(str(e)).to_dict()

        game.white_wolf_king_explode_target = target_id
        game.white_wolf_king_used_explode = True
        game.wolf_votes[player.seat_id] = -1  # Special marker
        game.add_action(player.seat_id, ActionType.SELF_DESTRUCT, target_id)
        return ActionResult.ok(t("action_result.self_destruct_success", language=game.language, target=target_id)).to_dict()

    return ActionResult.fail(
        t("api_responses.invalid_action_for_phase", language=game.language)
    ).to_dict()


def handle_guard_action(
    game: Game,
    player: Player,
    action_type: ActionType,
    target_id: Optional[int]
) -> dict:
    """Handle guard protect action."""
    if action_type != ActionType.PROTECT:
        return ActionResult.fail(
            t("api_responses.invalid_action_for_phase", language=game.language)
        ).to_dict()

    # Guard can skip by choosing target_id = 0
    if target_id == 0:
        game.guard_target = None
        game.guard_decided = True
        return ActionResult.ok(t("action_result.guard_skipped", language=game.language)).to_dict()

    if target_id is not None:
        try:
            validate_target(game, target_id, ActionType.PROTECT, player.seat_id, allow_abstain=False)
        except ValueError as e:
            return ActionResult.fail(str(e)).to_dict()

        # Check consecutive guard rule
        if target_id == game.guard_last_target:
            return ActionResult.fail(t("action_result.guard_consecutive", language=game.language)).to_dict()

        game.guard_target = target_id
        game.guard_decided = True
        game.add_action(player.seat_id, ActionType.PROTECT, target_id)
        return ActionResult.ok(t("action_result.guard_success", language=game.language, target=target_id)).to_dict()

    return ActionResult.fail(
        t("api_responses.invalid_action_for_phase", language=game.language)
    ).to_dict()


def handle_seer_action(
    game: Game,
    player: Player,
    action_type: ActionType,
    target_id: Optional[int]
) -> dict:
    """Handle seer verify action."""
    if action_type != ActionType.VERIFY or not target_id:
        return ActionResult.fail(
            t("api_responses.invalid_action_for_phase", language=game.language)
        ).to_dict()

    if game.seer_verified_this_night:
        return ActionResult.fail(
            t("api_responses.seer_already_verified", language=game.language)
        ).to_dict()

    if target_id == player.seat_id:
        return ActionResult.fail(
            t("api_responses.cannot_verify_self", language=game.language)
        ).to_dict()

    target = game.get_player(target_id)
    if target:
        is_wolf = target.role in WOLF_ROLES
        player.verified_players[target_id] = is_wolf
        game.seer_verified_this_night = True
        game.add_action(player.seat_id, ActionType.VERIFY, target_id)
        result = (
            t("prompts.seer_result_wolf", language=game.language)
            if is_wolf
            else t("prompts.seer_result_villager", language=game.language)
        )
        return ActionResult.ok(
            t("api_responses.seer_result", language=game.language, target_id=target_id, result=result)
        ).to_dict()

    return ActionResult.fail(
        t("api_responses.invalid_action_for_phase", language=game.language)
    ).to_dict()


def handle_witch_action(
    game: Game,
    player: Player,
    action_type: ActionType,
    target_id: Optional[int]
) -> dict:
    """Handle witch save/poison/skip actions."""
    used_save_this_night = any(
        a.day == game.day
        and a.player_id == player.seat_id
        and a.action_type == ActionType.SAVE
        for a in game.actions
    )

    if action_type == ActionType.SAVE:
        if game.witch_save_decided:
            return ActionResult.fail(
                t("api_responses.witch_save_decided", language=game.language)
            ).to_dict()
        if player.has_save_potion and game.night_kill_target:
            player.has_save_potion = False
            if game.night_kill_target in game.pending_deaths:
                game.pending_deaths.remove(game.night_kill_target)
            game.add_action(player.seat_id, ActionType.SAVE, game.night_kill_target)
            game.witch_save_decided = True
            game.witch_poison_decided = True  # Can't use both in same night
            return ActionResult.ok(
                t("api_responses.antidote_used", language=game.language)
            ).to_dict()
        return ActionResult.fail(
            t("api_responses.cannot_use_antidote", language=game.language)
        ).to_dict()

    elif action_type == ActionType.POISON and target_id:
        if not game.witch_save_decided:
            return ActionResult.fail(
                t("api_responses.decide_save_first", language=game.language)
            ).to_dict()
        if game.witch_poison_decided:
            return ActionResult.fail(
                t("api_responses.witch_poison_decided", language=game.language)
            ).to_dict()
        if used_save_this_night:
            return ActionResult.fail(
                t("api_responses.save_used_cannot_poison", language=game.language)
            ).to_dict()
        if player.has_poison_potion:
            try:
                validate_target(game, target_id, ActionType.POISON, player.seat_id)
            except ValueError as e:
                return ActionResult.fail(str(e)).to_dict()
            player.has_poison_potion = False
            game.pending_deaths.append(target_id)
            game.add_action(player.seat_id, ActionType.POISON, target_id)
            game.witch_poison_decided = True
            return ActionResult.ok(
                t("api_responses.poison_used", language=game.language)
            ).to_dict()
        return ActionResult.fail(
            t("api_responses.cannot_use_poison", language=game.language)
        ).to_dict()

    elif action_type == ActionType.SKIP:
        if not game.witch_save_decided:
            game.witch_save_decided = True
            return ActionResult.ok(
                t("api_responses.skip_antidote", language=game.language)
            ).to_dict()
        if not game.witch_poison_decided:
            game.witch_poison_decided = True
            return ActionResult.ok(
                t("api_responses.skip_poison", language=game.language)
            ).to_dict()
        return ActionResult.ok(
            t("api_responses.skip", language=game.language)
        ).to_dict()

    return ActionResult.fail(
        t("api_responses.invalid_action_for_phase", language=game.language)
    ).to_dict()
