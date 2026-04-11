from app.domain.enums import Role
from app.domain.game_context import GameContext


def resolve_seer_action(
    context: GameContext,
    *,
    seer_seat: int,
    target_seat: int,
) -> str:
    seer = context.players[seer_seat]
    target = context.players[target_seat]

    if not seer.is_alive or seer.role is not Role.SEER:
        raise ValueError("seer seat must belong to a living seer")
    if target_seat == seer_seat:
        raise ValueError("seer cannot inspect self")
    if not target.is_alive:
        raise ValueError("seer target must be alive")

    result = "狼人" if target.role is Role.WOLF else "好人"
    context.add_private_message(seer_seat, f"查验结果：{target_seat} 号是{result}。")
    return result
