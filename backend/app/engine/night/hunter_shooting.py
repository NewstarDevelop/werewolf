from dataclasses import dataclass

from app.domain.enums import Role
from app.domain.game_context import GameContext


@dataclass(slots=True, kw_only=True)
class HunterShotResult:
    can_shoot: bool
    shot_seat: int | None
    summary: str


def resolve_hunter_shooting(
    context: GameContext,
    *,
    hunter_seat: int,
    target_seat: int | None = None,
    poisoned: bool = False,
) -> HunterShotResult:
    hunter = context.players[hunter_seat]
    if hunter.role is not Role.HUNTER:
        raise ValueError("hunter seat must belong to a hunter")
    if hunter.is_alive:
        raise ValueError("hunter shooting requires a dead hunter")

    if poisoned:
        return HunterShotResult(
            can_shoot=False,
            shot_seat=None,
            summary=f"{hunter_seat}号猎人被毒死，无法开枪。",
        )

    if target_seat is None:
        raise ValueError("hunter target is required when hunter can shoot")
    if target_seat == hunter_seat:
        raise ValueError("hunter cannot shoot self")

    target = context.players[target_seat]
    if not target.is_alive:
        raise ValueError("hunter target must be alive")

    target.mark_dead()
    return HunterShotResult(
        can_shoot=True,
        shot_seat=target_seat,
        summary=f"{hunter_seat}号猎人开枪带走了{target_seat}号玩家。",
    )
