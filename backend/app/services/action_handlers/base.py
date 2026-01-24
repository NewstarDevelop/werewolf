"""Base utilities for action handlers."""
from typing import Optional
from app.models.game import Game, WOLF_ROLES
from app.schemas.enums import ActionType


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
    no_self_target_actions = [
        ActionType.KILL,      # MAJOR FIX: Add KILL to prevent wolves from voting themselves
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
