import random

from app.domain.game_context import GameContext
from app.engine.check_win import check_win
from app.engine.init import initialize_game
from app.engine.states.phase import GamePhase


class GameEngine:
    def __init__(self, *, rng: random.Random | None = None) -> None:
        self._rng = rng

    async def run_loop(
        self,
        *,
        context: GameContext | None = None,
        max_rounds: int = 1,
    ) -> GameContext:
        game_context = context

        if game_context is None:
            init_result = initialize_game(rng=self._rng)
            game_context = init_result.context

        game_context.phase = GamePhase.CHECK_WIN.value
        winner = check_win(game_context)
        if winner is not None:
            game_context.phase = GamePhase.GAME_OVER.value
            game_context.add_public_message(winner["summary"])
            return game_context

        for _ in range(max_rounds):
            game_context.phase = GamePhase.NIGHT_START.value
            game_context.killed_tonight.clear()
            game_context.add_public_message("天黑请闭眼。")

            game_context.phase = GamePhase.DAY_START.value
            game_context.add_public_message("天亮了，请开始发言。")

            game_context.phase = GamePhase.VOTING.value
            game_context.add_public_message("进入投票阶段。")

            winner = check_win(game_context)
            if winner is not None:
                game_context.phase = GamePhase.GAME_OVER.value
                game_context.add_public_message(winner["summary"])
                return game_context

        game_context.phase = GamePhase.GAME_OVER.value
        game_context.add_public_message("主流程骨架已跑通，等待夜晚与白天细分状态接入。")
        return game_context
