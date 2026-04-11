import asyncio

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import HumanPlayer, Player
from app.engine.game_engine import GameEngine
from app.engine.night.witch_action import WitchResources


def test_run_loop_uses_async_witch_action_selector() -> None:
    class HumanWitchEngine(GameEngine):
        async def _select_wolf_target(self, context: GameContext) -> int:
            return 4

        async def _select_witch_action(
            self,
            context: GameContext,
            *,
            witch_seat: int,
            resources: WitchResources,
            save_candidates: list[int],
            poison_candidates: list[int],
        ) -> tuple[int | None, int | None]:
            assert witch_seat == 1
            assert save_candidates == [4]
            assert poison_candidates == [2, 3]
            return None, 2

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
    context.add_player(HumanPlayer(seat_id=1, role=Role.WITCH))
    context.add_player(HumanPlayer(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.SEER))
    context.add_player(Player(seat_id=4, role=Role.VILLAGER))

    engine = HumanWitchEngine()
    final_context = asyncio.run(engine.run_loop(context=context, max_rounds=1))

    assert final_context.players[2].is_alive is False
