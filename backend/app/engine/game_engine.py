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

    async def _set_phase(self, context: GameContext, phase: GamePhase) -> None:
        context.phase = phase.value
        await self._notify_phase_changed(context)

    def _first_alive_seat_by_role(self, context: GameContext, role: Role) -> int | None:
        for seat_id, player in sorted(context.players.items()):
            if player.is_alive and player.role is role:
                return seat_id
        return None

    def _choose_wolf_target(self, context: GameContext) -> int:
        valid_targets = [
            seat_id
            for seat_id, player in sorted(context.players.items())
            if player.is_alive
        ]
        if not valid_targets:
            raise ValueError("no valid wolf target available")
        preferred_targets = [
            seat_id
            for seat_id in valid_targets
            if context.players[seat_id].role is not Role.WOLF
        ]
        fallback_targets = preferred_targets or valid_targets
        return self._rng.choice(fallback_targets) if self._rng else fallback_targets[0]

    async def _select_wolf_target(self, context: GameContext) -> int:
        human_wolf = next(
            (
                player
                for player in context.players.values()
                if isinstance(player, HumanPlayer)
                and player.is_alive
                and player.role is Role.WOLF
            ),
            None,
        )
        if human_wolf is not None or self._llm_client is None:
            return self._choose_wolf_target(context)

        alpha_wolf = next(
            (
                player
                for _, player in sorted(context.players.items())
                if isinstance(player, AIPlayer)
                and player.is_alive
                and player.role is Role.WOLF
            ),
            None,
        )
        valid_targets = [
            seat_id
            for seat_id, player in sorted(context.players.items())
            if player.is_alive
        ]
        if alpha_wolf is None or not valid_targets:
            return self._choose_wolf_target(context)

        response = self._llm_client.request_targeted_action(
            prompt=build_night_prompt(
                context,
                seat_id=alpha_wolf.seat_id,
                allowed_targets=valid_targets,
            ),
            allowed_targets=valid_targets,
        )
        if response.target in set(valid_targets):
            return response.target
        return self._choose_wolf_target(context)

    def _choose_hunter_target(self, context: GameContext, hunter_seat: int) -> int | None:
        valid_targets = [
            seat_id
            for seat_id, player in sorted(context.players.items())
            if player.is_alive and seat_id != hunter_seat
        ]
        if not valid_targets:
            return None
        return self._rng.choice(valid_targets) if self._rng else valid_targets[0]

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
        return self._rng.choice(valid_targets) if self._rng else valid_targets[0]

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
                prompt=build_night_prompt(
                    context,
                    seat_id=seer_seat,
                    allowed_targets=allowed_targets,
                ),
                allowed_targets=allowed_targets,
            )
            if response.target in set(allowed_targets):
                return response.target
        return self._rng.choice(allowed_targets) if self._rng else allowed_targets[0]

    async def _select_witch_action(
        self,
        context: GameContext,
        *,
        witch_seat: int,
        resources: WitchResources,
        save_candidates: list[int],
        poison_candidates: list[int],
    ) -> tuple[int | None, int | None]:
        player = context.players[witch_seat]
        if self._llm_client is not None and isinstance(player, AIPlayer):
            response = self._llm_client.request_targeted_action(
                prompt=build_night_prompt(
                    context,
                    seat_id=witch_seat,
                    allowed_targets=poison_candidates,
                ),
                allowed_targets=poison_candidates,
            )
            if response.use_antidote and save_candidates and resources.has_antidote:
                return save_candidates[0], None
            if (
                response.use_poison
                and resources.has_poison
                and response.target in set(poison_candidates)
            ):
                return None, response.target

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
        await self._set_phase(context, GamePhase.HUNTER_SHOOTING)
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
        if result.shot_seat is not None:
            await self._notify_player_state(context, [result.shot_seat])

        winner = check_win(context)
        if winner is None:
            return False

        await self._set_phase(context, GamePhase.GAME_OVER)
        context.add_public_message(winner["summary"])
        return True

    async def _run_last_words(
        self,
        context: GameContext,
        seat_ids: list[int],
    ) -> None:
        for seat_id in seat_ids:
            player = context.players.get(seat_id)
            if player is None:
                continue
            if isinstance(player, HumanPlayer):
                speech = await self._human_speaker(seat_id)
            elif self._llm_client is not None and isinstance(player, AIPlayer):
                speech = await self._llm_speaker(context, seat_id)
            else:
                speech = await self._ai_speaker(seat_id)
            context.add_public_message(f"{seat_id}号遗言：{speech}")

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
        if isinstance(player, HumanPlayer):
            return await self._human_speaker(seat_id)
        if self._llm_client is None or not isinstance(player, AIPlayer):
            return await self._ai_speaker(seat_id)

        response = self._llm_client.request_speech(
            prompt=build_speech_prompt(context, seat_id=seat_id),
        )
        return response.speech_text

    async def _notify_thinking(self, _: int, __: bool) -> None:
        return None

    async def _notify_player_state(
        self,
        _: GameContext,
        __: list[int],
    ) -> None:
        return None

    async def _notify_phase_changed(self, _: GameContext) -> None:
        return None

    async def _notify_death_revealed(
        self,
        _: GameContext,
        *,
        dead_seats: list[int],
        eligible_last_words: list[int],
    ) -> None:
        return None

    async def _notify_vote_resolved(
        self,
        *,
        votes: dict[int, int],
        abstentions: list[int],
        banished_seat: int | None,
        summary: str,
    ) -> None:
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
            prompt=build_vote_prompt(
                context,
                seat_id=seat_id,
                allowed_targets=allowed_targets,
            ),
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

        await self._set_phase(game_context, GamePhase.CHECK_WIN)
        winner = check_win(game_context)
        if winner is not None:
            await self._set_phase(game_context, GamePhase.GAME_OVER)
            game_context.add_public_message(winner["summary"])
            return game_context

        for _ in range(max_rounds):
            await self._set_phase(game_context, GamePhase.NIGHT_START)
            game_context.clear_night_deaths()
            game_context.add_public_message("天黑请闭眼。")

            await self._set_phase(game_context, GamePhase.WOLF_ACTION)
            wolf_target = await self._select_wolf_target(game_context)
            resolve_wolf_action(
                game_context,
                human_target=wolf_target,
                ai_target=wolf_target,
            )

            seer_seat = self._first_alive_seat_by_role(game_context, Role.SEER)
            if seer_seat is not None:
                await self._set_phase(game_context, GamePhase.SEER_ACTION)
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
                await self._set_phase(game_context, GamePhase.WITCH_ACTION)
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

            await self._set_phase(game_context, GamePhase.NIGHT_END)
            dead_hunters: list[tuple[int, bool]] = []
            night_dead_seats: list[int] = []
            for seat_id in list(game_context.killed_tonight):
                game_context.players[seat_id].mark_dead()
                night_dead_seats.append(seat_id)
                if game_context.players[seat_id].role is Role.HUNTER:
                    dead_hunters.append(
                        (
                            seat_id,
                            "poison" in game_context.death_causes_for(seat_id),
                        )
                    )
            await self._notify_player_state(game_context, night_dead_seats)

            await self._set_phase(game_context, GamePhase.DAY_START)
            announcement = announce_deaths_and_last_words(game_context)
            await self._notify_death_revealed(
                game_context,
                dead_seats=list(game_context.killed_tonight),
                eligible_last_words=announcement.eligible_last_words,
            )
            for hunter_seat, poisoned in dead_hunters:
                if await self._handle_hunter_shot(
                    game_context,
                    hunter_seat=hunter_seat,
                    poisoned=poisoned,
                ):
                    return game_context

            winner = check_win(game_context)
            if winner is not None:
                await self._set_phase(game_context, GamePhase.GAME_OVER)
                game_context.add_public_message(winner["summary"])
                return game_context

            if announcement.eligible_last_words:
                await self._set_phase(game_context, GamePhase.DEAD_LAST_WORDS)
                last_word_seats = [
                    seat_id
                    for seat_id in announcement.eligible_last_words
                    if seat_id in game_context.players
                    and not game_context.players[seat_id].is_alive
                ]
                if last_word_seats:
                    await self._run_last_words(game_context, last_word_seats)

            await self._set_phase(game_context, GamePhase.DAY_SPEAKING)
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

            await self._set_phase(game_context, GamePhase.VOTING)
            voting_result = resolve_voting(
                game_context,
                votes_by_voter=await self._build_votes(game_context),
            )
            await self._set_phase(game_context, GamePhase.VOTE_RESULT)
            game_context.add_public_message(voting_result.summary)
            banished_seat = voting_result.banished_seat
            await self._notify_vote_resolved(
                votes=voting_result.votes,
                abstentions=voting_result.abstentions,
                banished_seat=banished_seat,
                summary=voting_result.summary,
            )
            if banished_seat is not None:
                await self._notify_player_state(game_context, [banished_seat])
            if (
                banished_seat is not None
                and game_context.players[banished_seat].role is Role.HUNTER
            ):
                if await self._handle_hunter_shot(
                    game_context,
                    hunter_seat=banished_seat,
                ):
                    return game_context

            if (
                banished_seat is not None
                and banished_seat in game_context.players
                and not game_context.players[banished_seat].is_alive
            ):
                await self._set_phase(game_context, GamePhase.BANISH_LAST_WORDS)
                await self._run_last_words(game_context, [banished_seat])

            winner = check_win(game_context)
            if winner is not None:
                await self._set_phase(game_context, GamePhase.GAME_OVER)
                game_context.add_public_message(winner["summary"])
                return game_context

            game_context.day_count += 1

        await self._set_phase(game_context, GamePhase.GAME_OVER)
        game_context.add_public_message("夜尽未分胜负，本局暂止。")
        return game_context
