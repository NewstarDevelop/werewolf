from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import HumanPlayer, Player


def _living_targets(context: GameContext) -> list[Player]:
    return [
        player
        for _, player in sorted(context.players.items())
        if player.is_alive
    ]


def _default_wolf_target(context: GameContext, valid_targets: set[int]) -> int:
    non_wolf_targets = [
        player.seat_id
        for player in _living_targets(context)
        if player.role is not Role.WOLF and player.seat_id in valid_targets
    ]
    return min(non_wolf_targets or valid_targets)


def resolve_wolf_action(
    context: GameContext,
    *,
    human_target: int | None = None,
    ai_target: int | None = None,
) -> int:
    alive_wolves = [
        player
        for _, player in sorted(context.players.items())
        if player.is_alive and player.role is Role.WOLF
    ]
    if not alive_wolves:
        raise ValueError("no alive wolves available")

    valid_targets = {player.seat_id for player in _living_targets(context)}
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
            raise ValueError("human wolf target must be a living player")
        target_seat = human_target
    else:
        alpha_wolf = alive_wolves[0]
        if ai_target is not None:
            if ai_target not in valid_targets:
                raise ValueError("ai wolf target must be a living player")
            target_seat = ai_target
        else:
            target_seat = _default_wolf_target(context, valid_targets)
        context.add_private_message(alpha_wolf.seat_id, f"Alpha 狼决定击杀 {target_seat} 号。")

    context.mark_killed_tonight(target_seat, cause="wolf")
    return target_seat
