import asyncio

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import HumanPlayer, Player
from app.engine.game_engine import GameEngine


def test_handle_hunter_shot_uses_async_hunter_target_selector() -> None:
    class HumanHunterEngine(GameEngine):
        async def _select_hunter_target(
            self,
            context: GameContext,
            *,
            hunter_seat: int,
        ) -> int | None:
            assert hunter_seat == 1
            return 2

    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.HUNTER, is_alive=False))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.WOLF))
    context.add_player(Player(seat_id=4, role=Role.SEER))
    context.add_player(Player(seat_id=5, role=Role.VILLAGER))

    engine = HumanHunterEngine()
    resolved = asyncio.run(engine._handle_hunter_shot(context, hunter_seat=1))

    assert resolved is False
    assert context.players[2].is_alive is False
