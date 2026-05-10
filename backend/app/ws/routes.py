import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.domain.enums import Role
from app.domain.game_context import GameContext, PrivateChatEvent, PublicChatEvent, VoteSnapshot
from app.domain.player import HumanPlayer
from app.engine.check_win import check_win
from app.engine.game_engine import GameEngine
from app.llm.factory import build_default_llm_client
from app.protocols.c2s import ClientEnvelope
from app.protocols.s2c import (
    AIThinkingEnvelope,
    AIThinkingPayload,
    ChatUpdateEnvelope,
    ChatUpdatePayload,
    DeathRevealedEnvelope,
    DeathRevealedPayload,
    GameOverEnvelope,
    GameOverPayload,
    PhaseChangedEnvelope,
    PhaseChangedPayload,
    PlayerStatePatch,
    PlayerStatePatchEnvelope,
    PlayerStatePatchPayload,
    RequireInputEnvelope,
    RequireInputPayload,
    SettlementDayPayload,
    SettlementEventPayload,
    SettlementNightPayload,
    SettlementPlayerPayload,
    SettlementRecapPayload,
    SettlementSpeechPayload,
    SystemMessageEnvelope,
    SystemMessagePayload,
    VoteResolvedEnvelope,
    VoteResolvedPayload,
)
from app.services.setup_game import GameSetupResult, setup_game
from app.ws.manager import ConnectionManager

router = APIRouter()
manager = ConnectionManager()
logger = logging.getLogger(__name__)
SendJson = Callable[[dict[str, object]], Awaitable[None]]
CloseConnection = Callable[[], Awaitable[None]]
GAME_OVER_CLOSE_CODE = 4000
GAME_OVER_CLOSE_REASON = "game_over"
MAX_AI_THINKING_DELAY_SECONDS = 2.0
SETTLEMENT_EVENT_TYPES = {
    "NIGHT_DEATH",
    "PEACEFUL_NIGHT",
    "BANISHMENT",
    "VOTE_NO_BANISHMENT",
    "HUNTER_SHOT",
    "HUNTER_POISONED",
    "HUNTER_NO_TARGET",
    "LAST_WORDS",
    "GAME_OVER_SUMMARY",
}


def build_system_message(
    message: str,
    *,
    meta: dict[str, object] | None = None,
) -> dict[str, object]:
    return SystemMessageEnvelope(
        type="SYSTEM_MSG",
        data=SystemMessagePayload(message=message),
        meta=meta or {},
    ).model_dump()


def build_private_message(
    message: str,
    seat_id: int,
    *,
    meta: dict[str, object] | None = None,
) -> dict[str, object]:
    return ChatUpdateEnvelope(
        type="CHAT_UPDATE",
        data=ChatUpdatePayload(
            message=message,
            seat_id=seat_id,
            speaker="\u7cfb\u7edf",
            visibility="private",
        ),
        meta=meta or {},
    ).model_dump()


def build_public_message(
    message: str,
    *,
    meta: dict[str, object] | None = None,
) -> dict[str, object]:
    return ChatUpdateEnvelope(
        type="CHAT_UPDATE",
        data=ChatUpdatePayload(
            message=message,
            speaker="\u7cfb\u7edf",
            visibility="public",
        ),
        meta=meta or {},
    ).model_dump()


def build_public_chat_event_message(event: PublicChatEvent) -> dict[str, object]:
    meta: dict[str, object] = {}
    if event.message_kind != "system":
        meta["message_kind"] = event.message_kind
    if event.event_type is not None:
        meta["event_type"] = event.event_type
    if event.actor_seat is not None:
        meta["actor_seat"] = event.actor_seat
    if event.target_seats:
        meta["target_seats"] = event.target_seats

    return build_public_message(event.message, meta=meta)


def build_private_chat_event_message(event: PrivateChatEvent) -> dict[str, object]:
    meta: dict[str, object] = {}
    if event.event_type is not None:
        meta["event_type"] = event.event_type
    if event.target_seats:
        meta["target_seats"] = event.target_seats

    return build_private_message(event.message, event.seat_id, meta=meta)


def build_ai_thinking_message(seat_id: int, is_thinking: bool) -> dict[str, object]:
    return AIThinkingEnvelope(
        type="AI_THINKING",
        data=AIThinkingPayload(seat_id=seat_id, is_thinking=is_thinking),
    ).model_dump()


def build_player_state_patch_message(
    context: GameContext,
    seat_ids: list[int],
    *,
    reveal_roles: bool = False,
    reveal_role_seats: set[int] | None = None,
) -> dict[str, object]:
    role_seats = reveal_role_seats or set()
    return PlayerStatePatchEnvelope(
        type="PLAYER_STATE_PATCH",
        data=PlayerStatePatchPayload(
            players=[
                PlayerStatePatch(
                    seat_id=seat_id,
                    is_alive=context.players[seat_id].is_alive,
                    is_human=isinstance(context.players[seat_id], HumanPlayer),
                    role_code=(
                        context.players[seat_id].role.value
                        if reveal_roles or seat_id in role_seats
                        else None
                    ),
                    is_thinking=False,
                )
                for seat_id in seat_ids
            ],
        ),
    ).model_dump()


def known_role_seat_ids_from_setup(setup_result: GameSetupResult) -> list[int]:
    known_role_seats = [
        int(player_view["seat_id"])
        for player_view in setup_result.human_view["players"]
        if player_view.get("known_role") is not None
    ]
    return known_role_seats or [setup_result.human_seat_id]


def build_phase_changed_message(context: GameContext) -> dict[str, object]:
    return PhaseChangedEnvelope(
        type="PHASE_CHANGED",
        data=PhaseChangedPayload(
            phase=context.phase,
            day_count=context.day_count,
        ),
    ).model_dump()


def build_death_revealed_message(
    context: GameContext,
    *,
    dead_seats: list[int],
    eligible_last_words: list[int],
) -> dict[str, object]:
    return DeathRevealedEnvelope(
        type="DEATH_REVEALED",
        data=DeathRevealedPayload(
            dead_seats=dead_seats,
            eligible_last_words=eligible_last_words,
            day_count=context.day_count,
        ),
    ).model_dump()


def build_vote_resolved_message(
    *,
    votes: dict[int, int],
    ballots: dict[int, int] | None = None,
    abstentions: list[int],
    banished_seat: int | None,
    summary: str,
) -> dict[str, object]:
    return VoteResolvedEnvelope(
        type="VOTE_RESOLVED",
        data=VoteResolvedPayload(
            votes=votes,
            ballots=ballots or {},
            abstentions=abstentions,
            banished_seat=banished_seat,
            summary=summary,
        ),
    ).model_dump()


def build_require_input_message(
    action_type: Literal["SPEAK", "VOTE", "WOLF_KILL", "SEER_CHECK", "HUNTER_SHOOT", "WITCH_ACTION"],
    *,
    request_id: str,
    prompt: str,
    allowed_targets: list[int],
    available_actions: list[Literal["WITCH_SAVE", "WITCH_POISON", "PASS"]] | None = None,
    save_targets: list[int] | None = None,
) -> dict[str, object]:
    return RequireInputEnvelope(
        type="REQUIRE_INPUT",
        data=RequireInputPayload(
            action_type=action_type,
            request_id=request_id,
            prompt=prompt,
            allowed_targets=allowed_targets,
            available_actions=available_actions,
            save_targets=save_targets,
        ),
    ).model_dump(exclude_none=True)


def allowed_submit_action_types(
    action_type: Literal["SPEAK", "VOTE", "WOLF_KILL", "SEER_CHECK", "HUNTER_SHOOT", "WITCH_ACTION"],
    *,
    available_actions: list[Literal["WITCH_SAVE", "WITCH_POISON", "PASS"]] | None = None,
) -> set[str]:
    if action_type == "VOTE":
        return {"VOTE", "PASS"}
    if action_type == "WITCH_ACTION":
        if available_actions is None:
            return {"WITCH_SAVE", "WITCH_POISON", "PASS"}
        return set(available_actions)
    return {action_type}


def role_side(role: Role) -> Literal["GOOD", "WOLF"]:
    return "WOLF" if role is Role.WOLF else "GOOD"


def build_vote_payload(snapshot: VoteSnapshot) -> VoteResolvedPayload:
    return VoteResolvedPayload(
        votes=dict(snapshot.votes),
        ballots=dict(snapshot.ballots),
        abstentions=list(snapshot.abstentions),
        banished_seat=snapshot.banished_seat,
        summary=snapshot.summary,
    )


def explain_vote(snapshot: VoteSnapshot) -> str:
    if not snapshot.votes:
        return "所有玩家弃票，本轮无人出局。"

    highest_votes = max(snapshot.votes.values())
    leading_seats = [
        seat_id
        for seat_id, count in sorted(snapshot.votes.items())
        if count == highest_votes
    ]
    if snapshot.banished_seat is None:
        tied = "、".join(f"{seat_id}号" for seat_id in leading_seats)
        return f"最高票为 {highest_votes} 票，{tied} 平票，本轮无人出局。"
    return f"{snapshot.banished_seat}号以 {highest_votes} 票成为最高票，被放逐出局。"


def outcome_reason(winning_side: Literal["GOOD", "WOLF", "DRAW"], summary: str) -> str:
    if winning_side == "DRAW":
        return "达到回合上限仍未分出胜负，系统安全停局。"
    if "狼人已全部出局" in summary:
        return "狼人全灭。"
    if "平民已全部出局" in summary:
        return "平民屠边。"
    if "神职已全部出局" in summary:
        return "神职屠边。"
    return summary


def build_role_reveal_summary(context: GameContext) -> str:
    wolves = [
        seat_id
        for seat_id, player in sorted(context.players.items())
        if player.role is Role.WOLF
    ]
    gods = [
        seat_id
        for seat_id, player in sorted(context.players.items())
        if player.role in {Role.SEER, Role.WITCH, Role.HUNTER}
    ]
    villagers = [
        seat_id
        for seat_id, player in sorted(context.players.items())
        if player.role is Role.VILLAGER
    ]
    format_seats = lambda seats: "、".join(f"{seat_id}号" for seat_id in seats) or "无"
    return (
        f"狼人：{format_seats(wolves)}；"
        f"神职：{format_seats(gods)}；"
        f"平民：{format_seats(villagers)}。"
    )


def build_settlement_timeline(context: GameContext) -> list[SettlementEventPayload]:
    timeline: list[SettlementEventPayload] = []
    for event in context.public_chat_events:
        event_type = event.event_type
        if event_type is None and event.message_kind == "speech":
            event_type = "SPEECH"
        if event_type is None:
            event_type = "PUBLIC_MESSAGE"
        timeline.append(
            SettlementEventPayload(
                day_count=event.day_count,
                phase=event.phase,
                event_type=event_type,
                message=event.message,
                actor_seat=event.actor_seat,
                target_seats=list(event.target_seats),
            )
        )
    return timeline


def build_settlement_days(context: GameContext) -> list[SettlementDayPayload]:
    speeches_by_day: dict[int, list[SettlementSpeechPayload]] = {}
    for event in context.public_chat_events:
        if event.message_kind != "speech" or event.actor_seat is None:
            continue
        speeches_by_day.setdefault(event.day_count, []).append(
            SettlementSpeechPayload(
                seat_id=event.actor_seat,
                message=event.message,
                event_type=event.event_type or "SPEECH",
            )
        )

    from collections import defaultdict

    votes_by_day: dict[int, list[VoteSnapshot]] = defaultdict(list)
    for snapshot in context.vote_history:
        votes_by_day[snapshot.day_count].append(snapshot)
    day_numbers = sorted(set(speeches_by_day) | set(votes_by_day))

    return [
        SettlementDayPayload(
            day_count=day_count,
            speeches=speeches_by_day.get(day_count, []),
            vote=(
                build_vote_payload(votes_by_day[day_count][-1])
                if day_count in votes_by_day
                else None
            ),
            vote_explanation=(
                explain_vote(votes_by_day[day_count][-1])
                if day_count in votes_by_day
                else None
            ),
        )
        for day_count in day_numbers
    ]


def build_settlement_recap(context: GameContext) -> SettlementRecapPayload:
    winner = check_win(context)
    winning_side: Literal["GOOD", "WOLF", "DRAW"] = (
        winner["winning_side"] if winner is not None else "DRAW"
    )
    summary = winner["summary"] if winner is not None else (
        context.public_chat_history[-1]
        if context.public_chat_history
        else "夜尽未分胜负，本局暂止。"
    )
    final_vote = None
    if context.last_vote_result is not None:
        final_vote = build_vote_payload(context.last_vote_result)

    return SettlementRecapPayload(
        day_count=context.day_count,
        outcome_reason=outcome_reason(winning_side, summary),
        role_reveal_summary=build_role_reveal_summary(context),
        players=[
            SettlementPlayerPayload(
                seat_id=seat_id,
                role_code=player.role.value,
                side=role_side(player.role),
                is_alive=player.is_alive,
                is_human=isinstance(player, HumanPlayer),
            )
            for seat_id, player in sorted(context.players.items())
        ],
        nights=[
            SettlementNightPayload(
                day_count=night.day_count,
                wolf_target=night.wolf_target,
                seer_seat=night.seer_seat,
                seer_target=night.seer_target,
                seer_result=night.seer_result,
                witch_seat=night.witch_seat,
                witch_save_target=night.witch_save_target,
                witch_poison_target=night.witch_poison_target,
                dead_seats=list(night.dead_seats),
            )
            for night in context.night_actions
        ],
        days=build_settlement_days(context),
        key_events=[
            SettlementEventPayload(
                day_count=event.day_count,
                phase=event.phase,
                event_type=event.event_type,
                message=event.message,
                actor_seat=event.actor_seat,
                target_seats=list(event.target_seats),
            )
            for event in context.public_chat_events
            if event.event_type in SETTLEMENT_EVENT_TYPES
        ],
        timeline=build_settlement_timeline(context),
        final_vote=final_vote,
    )


def build_game_over_message(context: GameContext) -> dict[str, object] | None:
    winner = check_win(context)
    if winner is None and context.phase != "GAME_OVER":
        return None

    winning_side = winner["winning_side"] if winner is not None else "DRAW"
    summary = winner["summary"] if winner is not None else (
        context.public_chat_history[-1]
        if context.public_chat_history
        else "夜尽未分胜负，本局暂止。"
    )

    return GameOverEnvelope(
        type="GAME_OVER",
        data=GameOverPayload(
            winning_side=winning_side,
            summary=summary,
            revealed_roles={
                seat_id: player.role.value
                for seat_id, player in sorted(context.players.items())
            },
            recap=build_settlement_recap(context),
        ),
    ).model_dump()


def attach_context_bridge(
    context: GameContext,
    send_json: SendJson,
    *,
    viewer_seat_id: int,
) -> None:
    loop = asyncio.get_running_loop()

    context.on_public_chat_event(
        lambda event: loop.create_task(send_json(build_public_chat_event_message(event))),
    )
    context.on_private_chat_event(
        lambda event: (
            loop.create_task(send_json(build_private_chat_event_message(event)))
            if event.seat_id == viewer_seat_id
            else None
        ),
    )


def log_game_session_task_outcome(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.info("game session task cancelled")
    except Exception:
        logger.exception("game session task failed")


class WebSocketGameEngine(GameEngine):
    def __init__(
        self,
        *,
        send_json: SendJson,
        ai_thinking_delay_seconds: float = 0.0,
    ) -> None:
        super().__init__(
            llm_client=build_default_llm_client(),
            human_speech_timeout_seconds=None,
        )
        self._send_json = send_json
        self._active_context: GameContext | None = None
        self._input_request_counter = 0
        self._ai_thinking_delay_seconds = max(
            0.0,
            min(ai_thinking_delay_seconds, MAX_AI_THINKING_DELAY_SECONDS),
        )

    def _next_input_request_id(self) -> str:
        self._input_request_counter += 1
        return f"input-{self._input_request_counter}"

    async def _notify_thinking(self, seat_id: int, is_thinking: bool) -> None:
        await self._send_json(build_ai_thinking_message(seat_id, is_thinking))
        if is_thinking and self._ai_thinking_delay_seconds > 0:
            await asyncio.sleep(self._ai_thinking_delay_seconds)

    async def _notify_player_state(
        self,
        context: GameContext,
        seat_ids: list[int],
    ) -> None:
        if not seat_ids:
            return
        await self._send_json(build_player_state_patch_message(context, seat_ids))

    async def _notify_phase_changed(self, context: GameContext) -> None:
        await self._send_json(build_phase_changed_message(context))

    async def _notify_death_revealed(
        self,
        context: GameContext,
        *,
        dead_seats: list[int],
        eligible_last_words: list[int],
    ) -> None:
        await self._send_json(
            build_death_revealed_message(
                context,
                dead_seats=dead_seats,
                eligible_last_words=eligible_last_words,
            )
        )

    async def _notify_vote_resolved(
        self,
        *,
        votes: dict[int, int],
        ballots: dict[int, int] | None = None,
        abstentions: list[int],
        banished_seat: int | None,
        summary: str,
    ) -> None:
        await self._send_json(
            build_vote_resolved_message(
                votes=votes,
                ballots=ballots,
                abstentions=abstentions,
                banished_seat=banished_seat,
                summary=summary,
            )
        )

    async def _await_human_input(
        self,
        seat_id: int,
        *,
        action_type: Literal["SPEAK", "VOTE", "WOLF_KILL", "SEER_CHECK", "HUNTER_SHOOT", "WITCH_ACTION"],
        prompt: str,
        allowed_targets: list[int],
        available_actions: list[Literal["WITCH_SAVE", "WITCH_POISON", "PASS"]] | None = None,
        save_targets: list[int] | None = None,
    ) -> dict[str, object]:
        if self._active_context is None:
            return {}

        player = self._active_context.players[seat_id]
        if not isinstance(player, HumanPlayer):
            return {}

        request_id = self._next_input_request_id()
        pending_input = player.begin_input(
            allowed_action_types=allowed_submit_action_types(
                action_type,
                available_actions=available_actions,
            ),
            allowed_targets=set(allowed_targets),
            request_id=request_id,
        )
        try:
            await self._send_json(
                build_require_input_message(
                    action_type,
                    request_id=request_id,
                    prompt=prompt,
                    allowed_targets=allowed_targets,
                    available_actions=available_actions,
                    save_targets=save_targets,
                ),
            )
            return await pending_input
        finally:
            player.clear_input()

    async def _human_speaker(self, seat_id: int) -> str:
        if self._active_context is None:
            return await super()._human_speaker(seat_id)

        player = self._active_context.players[seat_id]
        if not isinstance(player, HumanPlayer):
            return await super()._human_speaker(seat_id)

        payload = await self._await_human_input(
            seat_id,
            action_type="SPEAK",
            prompt=f"\u8f6e\u5230\u4f60\u53d1\u8a00\uff0c\u8bf7\u4ee5 {seat_id} \u53f7\u73a9\u5bb6\u8eab\u4efd\u53d1\u8a00\u3002",
            allowed_targets=[],
        )
        return str(payload.get("text", "\u8fc7\u3002")).strip() or "\u8fc7\u3002"

    async def _human_vote(
        self,
        seat_id: int,
        *,
        allowed_targets: list[int],
    ) -> int | None:
        if self._active_context is None:
            return await super()._human_vote(seat_id, allowed_targets=allowed_targets)

        player = self._active_context.players[seat_id]
        if not isinstance(player, HumanPlayer):
            return await super()._human_vote(seat_id, allowed_targets=allowed_targets)

        payload = await self._await_human_input(
            seat_id,
            action_type="VOTE",
            prompt="\u8bf7\u9009\u62e9\u4e00\u540d\u5b58\u6d3b\u73a9\u5bb6\u4f5c\u4e3a\u653e\u9010\u76ee\u6807\u3002",
            allowed_targets=allowed_targets,
        )
        if payload.get("action_type") == "PASS":
            return None
        target = payload.get("target")
        if isinstance(target, int) and target in set(allowed_targets):
            return target
        return None

    async def _select_wolf_target(self, context: GameContext) -> int:
        human_player = next(
            (
                player
                for player in context.players.values()
                if isinstance(player, HumanPlayer)
                and player.is_alive
                and player.role is Role.WOLF
            ),
            None,
        )
        if human_player is None:
            return await super()._select_wolf_target(context)

        allowed_targets = [
            seat_id
            for seat_id, player in sorted(context.players.items())
            if player.is_alive
        ]
        payload = await self._await_human_input(
            human_player.seat_id,
            action_type="WOLF_KILL",
            prompt="\u8bf7\u9009\u62e9\u4eca\u591c\u8981\u51fb\u6740\u7684\u5b58\u6d3b\u73a9\u5bb6\u3002",
            allowed_targets=allowed_targets,
        )
        target = payload.get("target")
        if isinstance(target, int) and target in set(allowed_targets):
            context.add_private_message(
                human_player.seat_id,
                f"你选择今晚击杀 {target} 号。",
                event_type="NIGHT_ACTION_FEEDBACK",
                target_seats=[target],
            )
            return target
        return await super()._select_wolf_target(context)

    async def _select_seer_target(
        self,
        context: GameContext,
        *,
        seer_seat: int,
        allowed_targets: list[int],
    ) -> int:
        player = context.players[seer_seat]
        if not isinstance(player, HumanPlayer):
            return await super()._select_seer_target(
                context,
                seer_seat=seer_seat,
                allowed_targets=allowed_targets,
            )

        payload = await self._await_human_input(
            seer_seat,
            action_type="SEER_CHECK",
            prompt="\u8bf7\u9009\u62e9\u4eca\u591c\u8981\u67e5\u9a8c\u7684\u5b58\u6d3b\u73a9\u5bb6\u3002",
            allowed_targets=allowed_targets,
        )
        target = payload.get("target")
        if isinstance(target, int) and target in set(allowed_targets):
            context.add_private_message(
                seer_seat,
                f"你选择查验 {target} 号。",
                event_type="NIGHT_ACTION_FEEDBACK",
                target_seats=[target],
            )
            return target
        return await super()._select_seer_target(
            context,
            seer_seat=seer_seat,
            allowed_targets=allowed_targets,
        )

    async def _select_witch_action(
        self,
        context: GameContext,
        *,
        witch_seat: int,
        resources,
        save_candidates: list[int],
        poison_candidates: list[int],
    ) -> tuple[int | None, int | None]:
        player = context.players[witch_seat]
        if not isinstance(player, HumanPlayer):
            return await super()._select_witch_action(
                context,
                witch_seat=witch_seat,
                resources=resources,
                save_candidates=save_candidates,
                poison_candidates=poison_candidates,
            )

        prompt_parts: list[str] = []
        if save_candidates and resources.has_antidote:
            prompt_parts.append(f"\u6628\u591c {save_candidates[0]} \u53f7\u88ab\u51fb\u6740\uff0c\u4f60\u53ef\u4ee5\u9009\u62e9\u6551\u4eba\u3002")
        if resources.has_poison and poison_candidates:
            prompt_parts.append("\u4f60\u4e5f\u53ef\u4ee5\u9009\u62e9\u6bd2\u4eba\u6216\u8df3\u8fc7\u3002")
        prompt = " ".join(prompt_parts) or "\u8bf7\u9009\u62e9\u672c\u56de\u5408\u662f\u5426\u7528\u836f\u3002"
        available_actions: list[Literal["WITCH_SAVE", "WITCH_POISON", "PASS"]] = []
        save_targets = save_candidates if resources.has_antidote else []
        if save_targets:
            available_actions.append("WITCH_SAVE")
        if resources.has_poison and poison_candidates:
            available_actions.append("WITCH_POISON")
        available_actions.append("PASS")
        payload = await self._await_human_input(
            witch_seat,
            action_type="WITCH_ACTION",
            prompt=prompt,
            allowed_targets=poison_candidates,
            available_actions=available_actions,
            save_targets=save_targets,
        )

        action_type = payload.get("action_type")
        if action_type == "WITCH_SAVE" and save_candidates and resources.has_antidote:
            context.add_private_message(
                witch_seat,
                f"你使用解药救起 {save_candidates[0]} 号。",
                event_type="NIGHT_ACTION_FEEDBACK",
                target_seats=[save_candidates[0]],
            )
            return save_candidates[0], None
        if action_type == "WITCH_POISON":
            target = payload.get("target")
            if isinstance(target, int) and target in set(poison_candidates):
                context.add_private_message(
                    witch_seat,
                    f"你对 {target} 号使用毒药。",
                    event_type="NIGHT_ACTION_FEEDBACK",
                    target_seats=[target],
                )
                return None, target
        if action_type == "PASS":
            context.add_private_message(
                witch_seat,
                "你选择今晚不用药。",
                event_type="NIGHT_ACTION_FEEDBACK",
            )
            return None, None
        context.add_private_message(
            witch_seat,
            "无效的用药选择已忽略，本轮不使用药。",
            event_type="NIGHT_ACTION_FEEDBACK",
        )
        return None, None

    async def _select_hunter_target(
        self,
        context: GameContext,
        *,
        hunter_seat: int,
    ) -> int | None:
        player = context.players[hunter_seat]
        if not isinstance(player, HumanPlayer):
            return await super()._select_hunter_target(context, hunter_seat=hunter_seat)

        allowed_targets = [
            seat_id
            for seat_id, target in sorted(context.players.items())
            if target.is_alive and seat_id != hunter_seat
        ]
        payload = await self._await_human_input(
            hunter_seat,
            action_type="HUNTER_SHOOT",
            prompt="\u4f60\u53ef\u4ee5\u9009\u62e9\u4e00\u540d\u5b58\u6d3b\u73a9\u5bb6\u5f00\u67aa\u3002",
            allowed_targets=allowed_targets,
        )
        target = payload.get("target")
        if isinstance(target, int) and target in set(allowed_targets):
            return target
        return await super()._select_hunter_target(context, hunter_seat=hunter_seat)

    async def run_loop(
        self,
        *,
        context: GameContext | None = None,
        max_rounds: int = 1,
    ) -> GameContext:
        self._active_context = context
        try:
            return await super().run_loop(context=context, max_rounds=max_rounds)
        finally:
            self._active_context = None


async def run_game_session(
    setup_result: GameSetupResult,
    send_json: SendJson,
    *,
    close_connection: CloseConnection | None = None,
    engine: GameEngine | None = None,
    max_rounds: int = 20,
) -> None:
    active_engine = engine or WebSocketGameEngine(send_json=send_json)
    final_context = await active_engine.run_loop(
        context=setup_result.context,
        max_rounds=max_rounds,
    )
    logger.info("game session completed with phase=%s", final_context.phase)
    game_over_payload = build_game_over_message(final_context)
    if game_over_payload is not None:
        await send_json(game_over_payload)
        if close_connection is not None:
            await close_connection()


def resolve_human_submit_action(
    setup_result: GameSetupResult,
    payload: dict[str, object],
) -> bool:
    player = setup_result.context.players.get(setup_result.human_seat_id)
    if not isinstance(player, HumanPlayer):
        return False
    return player.resolve_input(payload)


def parse_ai_delay_seconds(raw_delay_ms: str | None) -> float:
    if raw_delay_ms is None:
        return 0.0
    try:
        delay_ms = int(raw_delay_ms)
    except ValueError:
        return 0.0
    return max(0.0, min(delay_ms / 1000, MAX_AI_THINKING_DELAY_SECONDS))


@router.websocket("/ws/game")
async def game_socket(websocket: WebSocket) -> None:
    setup_result = setup_game()
    ai_thinking_delay_seconds = parse_ai_delay_seconds(
        websocket.query_params.get("ai_delay_ms"),
    )

    await manager.connect(websocket)
    logger.info(
        "websocket connected human_seat=%s active_connections=%s",
        setup_result.human_seat_id,
        manager.active_connections,
    )
    attach_context_bridge(
        setup_result.context,
        lambda payload: manager.send_json(websocket, payload),
        viewer_seat_id=setup_result.human_seat_id,
    )
    await manager.send_json(websocket, build_system_message("connected"))
    await manager.send_json(
        websocket,
        build_public_message(setup_result.context.public_chat_history[0]),
    )
    await manager.send_json(
        websocket,
        build_private_message(
            setup_result.human_view["private_log"][-1],
            setup_result.human_seat_id,
        ),
    )
    known_role_seat_ids = known_role_seat_ids_from_setup(setup_result)
    await manager.send_json(
        websocket,
        build_player_state_patch_message(
            setup_result.context,
            known_role_seat_ids,
            reveal_role_seats=set(known_role_seat_ids),
        ),
    )
    await manager.send_json(websocket, build_phase_changed_message(setup_result.context))
    engine_task = asyncio.create_task(
        run_game_session(
            setup_result,
            lambda payload: manager.send_json(websocket, payload),
            close_connection=lambda: websocket.close(
                code=GAME_OVER_CLOSE_CODE,
                reason=GAME_OVER_CLOSE_REASON,
            ),
            engine=WebSocketGameEngine(
                send_json=lambda payload: manager.send_json(websocket, payload),
                ai_thinking_delay_seconds=ai_thinking_delay_seconds,
            ),
        ),
    )
    engine_task.add_done_callback(log_game_session_task_outcome)

    try:
        while True:
            raw_message = await websocket.receive_json()
            try:
                envelope = ClientEnvelope.model_validate(raw_message)
            except ValidationError:
                logger.warning("invalid websocket payload received")
                await manager.send_json(websocket, build_system_message("invalid payload"))
                continue

            action = envelope.data.action_type
            request_id = envelope.data.request_id
            resolved = resolve_human_submit_action(
                setup_result,
                envelope.data.model_dump(exclude_none=True),
            )
            if not resolved:
                logger.warning("unexpected websocket action ignored action=%s", action)
                meta: dict[str, object] = {
                    "status": "reject",
                    "action_type": action,
                }
                if request_id is not None:
                    meta["request_id"] = request_id
                await manager.send_json(
                    websocket,
                    build_system_message(f"reject:{action}", meta=meta),
                )
                continue
            meta = {
                "status": "ack",
                "action_type": action,
            }
            if request_id is not None:
                meta["request_id"] = request_id
            await manager.send_json(
                websocket,
                build_system_message(f"ack:{action}", meta=meta),
            )
    except WebSocketDisconnect:
        logger.info("websocket disconnected by client")
    finally:
        manager.disconnect(websocket)
        logger.info("websocket cleanup finished active_connections=%s", manager.active_connections)
        if not engine_task.done():
            engine_task.cancel()
