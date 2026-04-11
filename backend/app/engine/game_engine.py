import random

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.engine.day.day_speaking import run_day_speaking
from app.engine.check_win import check_win
from app.engine.day.dead_last_words import announce_deaths_and_last_words
from app.engine.day.voting import resolve_voting
from app.engine.init import initialize_game
from app.engine.night.hunter_shooting import resolve_hunter_shooting
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

    def _choose_hunter_target(self, context: GameContext, hunter_seat: int) -> int | None:
        valid_targets = [
            seat_id
            for seat_id, player in sorted(context.players.items())
            if player.is_alive and seat_id != hunter_seat
        ]
        if not valid_targets:
            return None
        return valid_targets[0]

    def _choose_witch_poison_target(
        self,
        context: GameContext,
        witch_seat: int,
        resources: WitchResources,
    ) -> int | None:
        if resources.has_antidote and context.killed_tonight:
            return None

        valid_targets = [
            seat_id
            for seat_id, player in sorted(context.players.items())
            if player.is_alive
            and seat_id != witch_seat
            and seat_id not in context.killed_tonight
        ]
        if not valid_targets:
            return None
        return valid_targets[0]

    def _handle_hunter_shot(
        self,
        context: GameContext,
        *,
        hunter_seat: int,
        poisoned: bool = False,
    ) -> bool:
        context.phase = GamePhase.HUNTER_SHOOTING.value
        target_seat = None if poisoned else self._choose_hunter_target(context, hunter_seat)

        if not poisoned and target_seat is None:
            context.add_public_message(f"{hunter_seat}号猎人死亡时场上已无可开枪目标。")
            return False

        result = resolve_hunter_shooting(
            context,
            hunter_seat=hunter_seat,
            target_seat=target_seat,
            poisoned=poisoned,
        )
        context.add_public_message(result.summary)

        winner = check_win(context)
        if winner is None:
            return False

        context.phase = GamePhase.GAME_OVER.value
        context.add_public_message(winner["summary"])
        return True

    async def _human_speaker(self, seat_id: int) -> str:
        return f"{seat_id}号选择过麦。"

    async def _ai_speaker(self, seat_id: int) -> str:
        return f"{seat_id}号正在陈述自己的判断。"

    async def _notify_thinking(self, _: int, __: bool) -> None:
        return None

    def _build_votes(self, context: GameContext) -> dict[int, int | None]:
        alive_seats = context.alive_seat_ids()
        votes: dict[int, int | None] = {}

        for seat_id in alive_seats:
            candidates = [candidate for candidate in alive_seats if candidate != seat_id]
            votes[seat_id] = candidates[0] if candidates else None

        return votes

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
            game_context.clear_night_deaths()
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
                    poison_target=(
                        self._choose_witch_poison_target(game_context, witch_seat, resources)
                        if resources.has_poison
                        else None
                    ),
                )

            game_context.phase = GamePhase.NIGHT_END.value
            dead_hunters: list[tuple[int, bool]] = []
            for seat_id in list(game_context.killed_tonight):
                game_context.players[seat_id].mark_dead()
                if game_context.players[seat_id].role is Role.HUNTER:
                    dead_hunters.append(
                        (
                            seat_id,
                            "poison" in game_context.death_causes_for(seat_id),
                        )
                    )

            game_context.phase = GamePhase.DAY_START.value
            announcement = announce_deaths_and_last_words(game_context)
            for hunter_seat, poisoned in dead_hunters:
                if self._handle_hunter_shot(
                    game_context,
                    hunter_seat=hunter_seat,
                    poisoned=poisoned,
                ):
                    return game_context
            if announcement.eligible_last_words:
                game_context.phase = GamePhase.DEAD_LAST_WORDS.value

            game_context.phase = GamePhase.DAY_SPEAKING.value
            alive_seats = game_context.alive_seat_ids()
            if alive_seats:
                await run_day_speaking(
                    game_context,
                    start_seat=alive_seats[0],
                    human_speaker=self._human_speaker,
                    ai_speaker=self._ai_speaker,
                    notify_thinking=self._notify_thinking,
                )

            game_context.phase = GamePhase.VOTING.value
            voting_result = resolve_voting(
                game_context,
                votes_by_voter=self._build_votes(game_context),
            )
            game_context.phase = GamePhase.VOTE_RESULT.value
            game_context.add_public_message(voting_result.summary)
            if (
                voting_result.banished_seat is not None
                and game_context.players[voting_result.banished_seat].role is Role.HUNTER
            ):
                if self._handle_hunter_shot(
                    game_context,
                    hunter_seat=voting_result.banished_seat,
                ):
                    return game_context

            winner = check_win(game_context)
            if winner is not None:
                game_context.phase = GamePhase.GAME_OVER.value
                game_context.add_public_message(winner["summary"])
                return game_context

            game_context.day_count += 1

        game_context.phase = GamePhase.GAME_OVER.value
        game_context.add_public_message("主流程骨架已跑通，等待夜晚与白天细分状态接入。")
        return game_context
