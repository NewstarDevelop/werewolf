import asyncio

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import HumanPlayer, Player
from app.engine.game_engine import GameEngine


def test_run_loop_uses_async_wolf_target_selector() -> None:
    class HumanWolfEngine(GameEngine):
        async def _select_wolf_target(self, context: GameContext) -> int:
            assert sorted(context.alive_seat_ids()) == [1, 2, 3]
            return 3

        async def _human_speaker(self, seat_id: int) -> str:
            return f"{seat_id}号发言：过。"

        async def _ai_speaker(self, seat_id: int) -> str:
            return f"{seat_id}号发言：过。"

        async def _human_vote(
            self,
            seat_id: int,
            *,
            allowed_targets: list[int],
        ) -> int | None:
            return 2

        async def _ai_vote(
            self,
            seat_id: int,
            *,
            allowed_targets: list[int],
        ) -> int | None:
            return 1

    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.WOLF))
    context.add_player(Player(seat_id=2, role=Role.SEER))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))

    engine = HumanWolfEngine()
    final_context = asyncio.run(engine.run_loop(context=context, max_rounds=1))

    assert final_context.players[3].is_alive is False
