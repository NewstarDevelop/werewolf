import random

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.engine.check_win import check_win
from app.engine.init import initialize_game
from app.engine.night.seer_action import resolve_seer_action
from app.engine.night.witch_action import WitchResources, resolve_witch_action
from app.engine.night.wolf_action import resolve_wolf_action
from app.engine.states.phase import GamePhase


class GameEngine:
    def __init__(self, *, rng: random.Random | None = None) -> None:
        self._rng = rng
        self._witch_resources: dict[int, WitchResources] = {}

    def _ensure_witch_resources(self, context: GameContext) -> None:
        for seat_id, player in context.players.items():
            if player.role is Role.WITCH:
                self._witch_resources.setdefault(seat_id, WitchResources())

    def _first_alive_seat_by_role(self, context: GameContext, role: Role) -> int | None:
        for seat_id, player in sorted(context.players.items()):
            if player.is_alive and player.role is role:
                return seat_id
        return None

    def _choose_wolf_target(self, context: GameContext) -> int:
        valid_targets = [
            seat_id
            for seat_id, player in sorted(context.players.items())
            if player.is_alive and player.role is not Role.WOLF
        ]
        if not valid_targets:
            raise ValueError("no valid wolf target available")
        return valid_targets[0]

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
        self._ensure_witch_resources(game_context)

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

            game_context.phase = GamePhase.WOLF_ACTION.value
            resolve_wolf_action(
                game_context,
                human_target=self._choose_wolf_target(game_context),
            )

            seer_seat = self._first_alive_seat_by_role(game_context, Role.SEER)
            if seer_seat is not None:
                game_context.phase = GamePhase.SEER_ACTION.value
                seer_targets = [
                    seat_id
                    for seat_id in game_context.alive_seat_ids()
                    if seat_id != seer_seat
                ]
                if seer_targets:
                    resolve_seer_action(
                        game_context,
                        seer_seat=seer_seat,
                        target_seat=seer_targets[0],
                    )

            witch_seat = self._first_alive_seat_by_role(game_context, Role.WITCH)
            if witch_seat is not None:
                game_context.phase = GamePhase.WITCH_ACTION.value
                resources = self._witch_resources[witch_seat]
                save_candidates = [
                    seat_id
                    for seat_id in game_context.killed_tonight
                    if seat_id != witch_seat
                ]
                resolve_witch_action(
                    game_context,
                    witch_seat=witch_seat,
                    resources=resources,
                    save_target=save_candidates[0] if save_candidates and resources.has_antidote else None,
                )

            game_context.phase = GamePhase.NIGHT_END.value
            for seat_id in list(game_context.killed_tonight):
                game_context.players[seat_id].mark_dead()

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
