import asyncio

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import HumanPlayer, Player
from app.engine.game_engine import GameEngine


def test_run_loop_uses_async_hunter_target_selector() -> None:
    class HumanHunterEngine(GameEngine):
        async def _select_wolf_target(self, context: GameContext) -> int:
            return 1

        async def _select_hunter_target(
            self,
            context: GameContext,
            *,
            hunter_seat: int,
        ) -> int | None:
            assert hunter_seat == 1
            assert sorted(context.alive_seat_ids()) == [2, 3, 4, 5]
            return 2

        async def _human_speaker(self, seat_id: int) -> str:
            return f"{seat_id}号发言：过。"

        async def _ai_speaker(self, seat_id: int) -> str:
            return f"{seat_id}号发言：过。"

    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.HUNTER))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.WOLF))
    context.add_player(Player(seat_id=4, role=Role.SEER))
    context.add_player(Player(seat_id=5, role=Role.VILLAGER))

    engine = HumanHunterEngine()
    final_context = asyncio.run(engine.run_loop(context=context, max_rounds=1))

    assert final_context.players[1].is_alive is False
    assert final_context.players[2].is_alive is False
    assert "1号猎人开枪带走了2号玩家。" in final_context.public_chat_history
