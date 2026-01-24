"""Shoot phase action handlers for human players."""
from typing import Optional
from app.models.game import Game, Player
from app.schemas.enums import ActionType, MessageType, Role
from app.i18n import t
from app.services.phase_handlers import continue_after_hunter
from .base import validate_target, ActionResult


def handle_death_shoot_action(
    game: Game,
    player: Player,
    action_type: ActionType,
    target_id: Optional[int]
) -> dict:
    """Handle death shoot action (hunter or wolf king)."""
    # MAJOR FIX: Accept both SHOOT and SKIP for consistency with game_engine.py:164
    if action_type not in (ActionType.SHOOT, ActionType.SKIP):
        return ActionResult.fail(
            t("api_responses.invalid_action_for_phase", language=game.language)
        ).to_dict()

    # Only hunter or wolf king can shoot in this phase
    if player.role not in [Role.HUNTER, Role.WOLF_KING]:
        return ActionResult.fail("只有猎人或狼王可以在此阶段开枪").to_dict()

    seat_suffix = "号" if game.language == "zh" else ""
    shooter_name = "猎人" if player.role == Role.HUNTER else "狼王"

    # Skip shooting (SKIP action or target_id = 0)
    if action_type == ActionType.SKIP or target_id == 0:
        abstain_message = f"{shooter_name}{player.seat_id}{seat_suffix}放弃开枪"
        game.add_message(0, abstain_message, MessageType.SYSTEM)
        return ActionResult.ok("已放弃开枪").to_dict()

    # Validate and execute shoot
    if target_id is not None:
        try:
            validate_target(game, target_id, ActionType.SHOOT, player.seat_id, allow_abstain=False)
        except ValueError as e:
            return ActionResult.fail(str(e)).to_dict()

        shoot_message = f"{shooter_name}{player.seat_id}{seat_suffix}开枪带走了{target_id}{seat_suffix}"
        game.add_message(0, shoot_message, MessageType.SYSTEM)
        game.kill_player(target_id)
        game.add_action(player.seat_id, ActionType.SHOOT, target_id)
        return ActionResult.ok(f"已射击{target_id}号玩家").to_dict()

    return ActionResult.fail(
        t("api_responses.invalid_action_for_phase", language=game.language)
    ).to_dict()


def handle_hunter_shoot_action(
    game: Game,
    player: Player,
    action_type: ActionType,
    target_id: Optional[int]
) -> dict:
    """Handle legacy hunter shoot action (backward compatibility)."""
    if game.current_actor_seat != player.seat_id:
        return ActionResult.fail(
            t("api_responses.not_your_turn", language=game.language)
        ).to_dict()

    if not player.can_shoot:
        return ActionResult.fail(
            t("api_responses.cannot_shoot", language=game.language)
        ).to_dict()

    seat_suffix = "号" if game.language == "zh" else ""

    if action_type == ActionType.SHOOT and target_id:
        try:
            validate_target(game, target_id, ActionType.SHOOT, player.seat_id)
        except ValueError as e:
            return ActionResult.fail(str(e)).to_dict()

        game.add_message(
            0,
            t(
                "system_messages.hunter_shot",
                language=game.language,
                hunter_id=f"{player.seat_id}{seat_suffix}",
                target_id=f"{target_id}{seat_suffix}"
            ),
            MessageType.SYSTEM
        )
        game.kill_player(target_id)
        game.add_action(player.seat_id, ActionType.SHOOT, target_id)

        result = ActionResult.ok(
            t("api_responses.hunter_shot_player", language=game.language, target_id=target_id)
        ).to_dict()
        result.update(continue_after_hunter(game))
        return result

    if action_type == ActionType.SKIP:
        game.add_message(
            0,
            t(
                "system_messages.hunter_abstain",
                language=game.language,
                seat_id=f"{player.seat_id}{seat_suffix}"
            ),
            MessageType.SYSTEM
        )
        result = ActionResult.ok(
            t("api_responses.hunter_abstain_shoot", language=game.language)
        ).to_dict()
        result.update(continue_after_hunter(game))
        return result

    return ActionResult.fail(
        t("api_responses.invalid_action_for_phase", language=game.language)
    ).to_dict()
