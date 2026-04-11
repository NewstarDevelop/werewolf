import asyncio

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import HumanPlayer, Player
from app.engine.game_engine import GameEngine


def test_build_votes_uses_human_vote_when_collecting_ballots() -> None:
    class HumanVoteEngine(GameEngine):
        async def _human_vote(
            self,
            seat_id: int,
            *,
            allowed_targets: list[int],
        ) -> int | None:
            assert seat_id == 1
            assert allowed_targets == [2, 3]
            return 3

        async def _ai_vote(
            self,
            seat_id: int,
            *,
            allowed_targets: list[int],
        ) -> int | None:
            return 3 if seat_id == 2 else 1

    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.VILLAGER))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.SEER))

    engine = HumanVoteEngine()
    votes = asyncio.run(engine._build_votes(context))

    assert votes == {1: 3, 2: 3, 3: 1}
