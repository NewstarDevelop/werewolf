import asyncio

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import HumanPlayer, Player
from app.engine.game_engine import GameEngine


def test_run_loop_uses_async_seer_target_selector() -> None:
    class HumanSeerEngine(GameEngine):
        async def _select_seer_target(
            self,
            context: GameContext,
            *,
            seer_seat: int,
            allowed_targets: list[int],
        ) -> int:
            assert seer_seat == 1
            assert allowed_targets == [2, 3]
            return 2

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
    context.add_player(HumanPlayer(seat_id=1, role=Role.SEER))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))

    engine = HumanSeerEngine()
    final_context = asyncio.run(engine.run_loop(context=context, max_rounds=1))

    assert any("\u67e5\u9a8c\u7ed3\u679c" in message for message in final_context.get_private_log(1))
