import random

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer, HumanPlayer
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
from app.llm.builders import build_night_prompt, build_speech_prompt, build_vote_prompt
from app.llm.fallback import FallbackLLMClient


class GameEngine:
    def __init__(
        self,
        *,
        rng: random.Random | None = None,
        llm_client: FallbackLLMClient | None = None,
    ) -> None:
        self._rng = rng
        self._llm_client = llm_client
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

    async def _select_wolf_target(self, context: GameContext) -> int:
        return self._choose_wolf_target(context)

    def _choose_hunter_target(self, context: GameContext, hunter_seat: int) -> int | None:
        valid_targets = [
            seat_id
            for seat_id, player in sorted(context.players.items())
            if player.is_alive and seat_id != hunter_seat
        ]
        if not valid_targets:
            return None
        return valid_targets[0]

    async def _select_hunter_target(
        self,
        context: GameContext,
        *,
        hunter_seat: int,
    ) -> int | None:
        return self._choose_hunter_target(context, hunter_seat)

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

    async def _select_seer_target(
        self,
        context: GameContext,
        *,
        seer_seat: int,
        allowed_targets: list[int],
    ) -> int:
        player = context.players[seer_seat]
        if self._llm_client is not None and isinstance(player, AIPlayer):
            response = self._llm_client.request_targeted_action(
                prompt=build_night_prompt(context, seat_id=seer_seat),
                allowed_targets=allowed_targets,
            )
            if response.target in set(allowed_targets):
                return response.target
        return allowed_targets[0]

    async def _select_witch_action(
        self,
        context: GameContext,
        *,
        witch_seat: int,
        resources: WitchResources,
        save_candidates: list[int],
        poison_candidates: list[int],
    ) -> tuple[int | None, int | None]:
        save_target = save_candidates[0] if save_candidates and resources.has_antidote else None
        poison_target = (
            self._choose_witch_poison_target(context, witch_seat, resources)
            if poison_candidates and resources.has_poison
            else None
        )
        if save_target is not None:
            poison_target = None
        return save_target, poison_target

    async def _handle_hunter_shot(
        self,
        context: GameContext,
        *,
        hunter_seat: int,
        poisoned: bool = False,
    ) -> bool:
        context.phase = GamePhase.HUNTER_SHOOTING.value
        target_seat = None if poisoned else await self._select_hunter_target(
            context,
            hunter_seat=hunter_seat,
        )

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

    async def _human_vote(
        self,
        seat_id: int,
        *,
        allowed_targets: list[int],
    ) -> int | None:
        return allowed_targets[0] if allowed_targets else None

    async def _ai_vote(
        self,
        seat_id: int,
        *,
        allowed_targets: list[int],
    ) -> int | None:
        return allowed_targets[0] if allowed_targets else None

    async def _ai_speaker(self, seat_id: int) -> str:
        return f"{seat_id}号正在陈述自己的判断。"

    async def _llm_speaker(self, context: GameContext, seat_id: int) -> str:
        player = context.players[seat_id]
        if self._llm_client is None or not isinstance(player, AIPlayer):
            return await self._ai_speaker(seat_id)

        response = self._llm_client.request_speech(
            prompt=build_speech_prompt(context, seat_id=seat_id),
        )
        return response.speech_text

    async def _notify_thinking(self, _: int, __: bool) -> None:
        return None

    async def _llm_vote(
        self,
        context: GameContext,
        seat_id: int,
        *,
        allowed_targets: list[int],
    ) -> int | None:
        player = context.players[seat_id]
        if self._llm_client is None or not isinstance(player, AIPlayer):
            return await self._ai_vote(seat_id, allowed_targets=allowed_targets)

        response = self._llm_client.request_vote(
            prompt=build_vote_prompt(context, seat_id=seat_id),
            allowed_targets=allowed_targets,
        )
        return None if response.vote_target == 0 else response.vote_target

    async def _build_votes(self, context: GameContext) -> dict[int, int | None]:
        alive_seats = context.alive_seat_ids()
        votes: dict[int, int | None] = {}

        for seat_id in alive_seats:
            candidates = [candidate for candidate in alive_seats if candidate != seat_id]
            player = context.players[seat_id]
            if isinstance(player, HumanPlayer):
                votes[seat_id] = await self._human_vote(
                    seat_id,
                    allowed_targets=candidates,
                )
                continue

            votes[seat_id] = (
                await self._llm_vote(
                    context,
                    seat_id,
                    allowed_targets=candidates,
                )
                if self._llm_client is not None
                else await self._ai_vote(
                    seat_id,
                    allowed_targets=candidates,
                )
            )

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
                human_target=await self._select_wolf_target(game_context),
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
                        target_seat=await self._select_seer_target(
                            game_context,
                            seer_seat=seer_seat,
                            allowed_targets=seer_targets,
                        ),
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
                poison_candidates = [
                    seat_id
                    for seat_id, player in sorted(game_context.players.items())
                    if player.is_alive
                    and seat_id != witch_seat
                    and seat_id not in game_context.killed_tonight
                ]
                save_target, poison_target = await self._select_witch_action(
                    game_context,
                    witch_seat=witch_seat,
                    resources=resources,
                    save_candidates=save_candidates,
                    poison_candidates=poison_candidates,
                )
                resolve_witch_action(
                    game_context,
                    witch_seat=witch_seat,
                    resources=resources,
                    save_target=save_target,
                    poison_target=poison_target,
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
                if await self._handle_hunter_shot(
                    game_context,
                    hunter_seat=hunter_seat,
                    poisoned=poisoned,
                ):
                    return game_context

            winner = check_win(game_context)
            if winner is not None:
                game_context.phase = GamePhase.GAME_OVER.value
                game_context.add_public_message(winner["summary"])
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
                    ai_speaker=(
                        self._ai_speaker
                        if self._llm_client is None
                        else lambda seat_id: self._llm_speaker(game_context, seat_id)
                    ),
                    notify_thinking=self._notify_thinking,
                )

            game_context.phase = GamePhase.VOTING.value
            voting_result = resolve_voting(
                game_context,
                votes_by_voter=await self._build_votes(game_context),
            )
            game_context.phase = GamePhase.VOTE_RESULT.value
            game_context.add_public_message(voting_result.summary)
            if (
                voting_result.banished_seat is not None
                and game_context.players[voting_result.banished_seat].role is Role.HUNTER
            ):
                if await self._handle_hunter_shot(
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
