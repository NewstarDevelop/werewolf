from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import HumanPlayer, Player


def _living_non_wolf_targets(context: GameContext) -> list[Player]:
    return [
        player
        for _, player in sorted(context.players.items())
        if player.is_alive and player.role is not Role.WOLF
    ]


def resolve_wolf_action(
    context: GameContext,
    *,
    human_target: int | None = None,
) -> int:
    alive_wolves = [
        player
        for _, player in sorted(context.players.items())
        if player.is_alive and player.role is Role.WOLF
    ]
    if not alive_wolves:
        raise ValueError("no alive wolves available")

    valid_targets = {player.seat_id for player in _living_non_wolf_targets(context)}
    if not valid_targets:
        raise ValueError("no valid wolf targets available")

    human_wolf = next(
        (
            player
            for player in alive_wolves
            if isinstance(player, HumanPlayer)
        ),
        None,
    )

    if human_wolf is not None:
        if human_target is None or human_target not in valid_targets:
            raise ValueError("human wolf target must be a living non-wolf player")
        target_seat = human_target
    else:
        alpha_wolf = alive_wolves[0]
        target_seat = min(valid_targets)
        context.add_private_message(alpha_wolf.seat_id, f"Alpha 狼决定击杀 {target_seat} 号。")

    context.mark_killed_tonight(target_seat, cause="wolf")
    return target_seat
