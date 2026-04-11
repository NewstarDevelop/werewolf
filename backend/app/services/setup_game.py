import random
from dataclasses import dataclass
from typing import Any

from app.engine.init import initialize_game
from app.domain.game_context import GameContext
from app.domain.view_mask import build_player_view


@dataclass(slots=True, kw_only=True)
class GameSetupResult:
    context: GameContext
    human_seat_id: int
    human_role: str
    human_view: dict[str, Any]


def setup_game(*, rng: random.Random | None = None) -> GameSetupResult:
    init_result = initialize_game(rng=rng)
    identity_message = (
        f"你的座位号是 {init_result.human_seat_id} 号，身份是 {init_result.human_role.value}。"
    )
    init_result.context.add_private_message(init_result.human_seat_id, identity_message)

    return GameSetupResult(
        context=init_result.context,
        human_seat_id=init_result.human_seat_id,
        human_role=init_result.human_role.value,
        human_view=build_player_view(init_result.context, init_result.human_seat_id),
    )
