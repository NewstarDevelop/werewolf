from typing import Any

from app.domain.enums import Role
from app.domain.game_context import GameContext


def build_player_view(context: GameContext, viewer_seat: int) -> dict[str, Any]:
    viewer = context.players[viewer_seat]
    known_wolf_seats = set[int]()

    if viewer.role is Role.WOLF:
        known_wolf_seats = {
            player.seat_id
            for player in context.players.values()
            if player.role is Role.WOLF
        }

    players_view = []
    for seat_id, player in sorted(context.players.items()):
        known_role: str | None = None
        if seat_id == viewer_seat:
            known_role = player.role.value
        elif seat_id in known_wolf_seats:
            known_role = Role.WOLF.value

        players_view.append(
            {
                "seat_id": seat_id,
                "is_alive": player.is_alive,
                "is_self": seat_id == viewer_seat,
                "known_role": known_role,
            }
        )

    return {
        "day_count": context.day_count,
        "phase": context.phase,
        "players": players_view,
        "public_chat_history": list(context.public_chat_history),
        "killed_tonight": list(context.killed_tonight),
        "private_log": context.get_private_log(viewer_seat),
    }
