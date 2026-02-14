"""Base utilities for action handlers."""
from app.models.game import Game
from app.schemas.enums import ActionType
from app.i18n import t


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
    lang = game.language

    # Allow abstain/skip (target_id = 0) if permitted
    if target_id == 0:
        if allow_abstain:
            return
        raise ValueError(t("validation.invalid_target_zero", language=lang))

    # Check if target seat exists
    if target_id not in game.players:
        raise ValueError(t("validation.player_not_exist", language=lang, target=target_id))

    target_player = game.get_player(target_id)
    if not target_player:
        raise ValueError(t("validation.player_not_exist", language=lang, target=target_id))

    # Check if target is alive (required for most actions)
    if not target_player.is_alive:
        raise ValueError(t("validation.player_dead", language=lang, target=target_id))

    # Prevent self-targeting for certain actions
    # Note: KILL is intentionally excluded — wolves may self-kill
    no_self_target_actions = [
        ActionType.POISON,
        ActionType.VOTE,
        ActionType.SHOOT,
        ActionType.VERIFY
    ]

    if action_type in no_self_target_actions and target_id == actor_seat:
        action_names = {
            ActionType.POISON: t("validation.action_poison", language=lang),
            ActionType.VOTE: t("validation.action_vote", language=lang),
            ActionType.SHOOT: t("validation.action_shoot", language=lang),
            ActionType.VERIFY: t("validation.action_verify", language=lang),
        }
        action_name = action_names.get(action_type, t("validation.action_default", language=lang))
        raise ValueError(t("validation.cannot_self_target", language=lang, action=action_name))


class ActionResult:
    """Standardized action result."""
    
    def __init__(self, success: bool, message: str, **extra):
        self.success = success
        self.message = message
        self.extra = extra
    
    def to_dict(self) -> dict:
        result = {"success": self.success, "message": self.message}
        result.update(self.extra)
        return result
    
    @classmethod
    def ok(cls, message: str, **extra) -> "ActionResult":
        return cls(True, message, **extra)
    
    @classmethod
    def fail(cls, message: str) -> "ActionResult":
        return cls(False, message)
