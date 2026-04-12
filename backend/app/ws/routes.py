import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.domain.enums import Role
from app.domain.game_context import GameContext
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
    GameOverEnvelope,
    GameOverPayload,
    RequireInputEnvelope,
    RequireInputPayload,
    SystemMessageEnvelope,
    SystemMessagePayload,
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


def build_system_message(message: str) -> dict[str, object]:
    return SystemMessageEnvelope(
        type="SYSTEM_MSG",
        data=SystemMessagePayload(message=message),
    ).model_dump()


def build_private_message(message: str, seat_id: int) -> dict[str, object]:
    return ChatUpdateEnvelope(
        type="CHAT_UPDATE",
        data=ChatUpdatePayload(
            message=message,
            seat_id=seat_id,
            speaker="\u7cfb\u7edf",
            visibility="private",
        ),
    ).model_dump()


def build_public_message(message: str) -> dict[str, object]:
    return ChatUpdateEnvelope(
        type="CHAT_UPDATE",
        data=ChatUpdatePayload(
            message=message,
            speaker="\u7cfb\u7edf",
            visibility="public",
        ),
    ).model_dump()


def build_ai_thinking_message(seat_id: int, is_thinking: bool) -> dict[str, object]:
    return AIThinkingEnvelope(
        type="AI_THINKING",
        data=AIThinkingPayload(seat_id=seat_id, is_thinking=is_thinking),
    ).model_dump()


def build_require_input_message(
    action_type: Literal["SPEAK", "VOTE", "WOLF_KILL", "SEER_CHECK", "HUNTER_SHOOT", "WITCH_ACTION"],
    *,
    prompt: str,
    allowed_targets: list[int],
) -> dict[str, object]:
    return RequireInputEnvelope(
        type="REQUIRE_INPUT",
        data=RequireInputPayload(
            action_type=action_type,
            prompt=prompt,
            allowed_targets=allowed_targets,
        ),
    ).model_dump()


def build_game_over_message(context: GameContext) -> dict[str, object] | None:
    winner = check_win(context)
    if winner is None:
        return None

    return GameOverEnvelope(
        type="GAME_OVER",
        data=GameOverPayload(
            winning_side=winner["winning_side"],
            summary=winner["summary"],
            revealed_roles={
                seat_id: player.role.value
                for seat_id, player in sorted(context.players.items())
            },
        ),
    ).model_dump()


def attach_context_bridge(context: GameContext, send_json: SendJson) -> None:
    loop = asyncio.get_running_loop()

    context.on_public_message(
        lambda message: loop.create_task(send_json(build_public_message(message))),
    )
    context.on_private_message(
        lambda seat_id, message: loop.create_task(send_json(build_private_message(message, seat_id))),
    )


def log_game_session_task_outcome(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.info("game session task cancelled")
    except Exception:
        logger.exception("game session task failed")


class WebSocketGameEngine(GameEngine):
    def __init__(self, *, send_json: SendJson) -> None:
        super().__init__(llm_client=build_default_llm_client())
        self._send_json = send_json
        self._active_context: GameContext | None = None

    async def _notify_thinking(self, seat_id: int, is_thinking: bool) -> None:
        await self._send_json(build_ai_thinking_message(seat_id, is_thinking))

    async def _await_human_input(
        self,
        seat_id: int,
        *,
        action_type: Literal["SPEAK", "VOTE", "WOLF_KILL", "SEER_CHECK", "HUNTER_SHOOT", "WITCH_ACTION"],
        prompt: str,
        allowed_targets: list[int],
    ) -> dict[str, object]:
        if self._active_context is None:
            return {}

        player = self._active_context.players[seat_id]
        if not isinstance(player, HumanPlayer):
            return {}

        pending_input = player.begin_input()
        try:
            await self._send_json(
                build_require_input_message(
                    action_type,
                    prompt=prompt,
                    allowed_targets=allowed_targets,
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
            if player.is_alive and player.role is not Role.WOLF
        ]
        payload = await self._await_human_input(
            human_player.seat_id,
            action_type="WOLF_KILL",
            prompt="\u8bf7\u9009\u62e9\u4eca\u591c\u8981\u51fb\u6740\u7684\u5b58\u6d3b\u73a9\u5bb6\u3002",
            allowed_targets=allowed_targets,
        )
        target = payload.get("target")
        if isinstance(target, int) and target in set(allowed_targets):
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
        if resources.has_poison:
            prompt_parts.append("\u4f60\u4e5f\u53ef\u4ee5\u9009\u62e9\u6bd2\u4eba\u6216\u8df3\u8fc7\u3002")
        prompt = " ".join(prompt_parts) or "\u8bf7\u9009\u62e9\u672c\u56de\u5408\u662f\u5426\u7528\u836f\u3002"
        payload = await self._await_human_input(
            witch_seat,
            action_type="WITCH_ACTION",
            prompt=prompt,
            allowed_targets=poison_candidates,
        )

        action_type = payload.get("action_type")
        if action_type == "WITCH_SAVE" and save_candidates and resources.has_antidote:
            return save_candidates[0], None
        if action_type == "WITCH_POISON":
            target = payload.get("target")
            if isinstance(target, int) and target in set(poison_candidates):
                return None, target
        if action_type == "PASS":
            return None, None
        return await super()._select_witch_action(
            context,
            witch_seat=witch_seat,
            resources=resources,
            save_candidates=save_candidates,
            poison_candidates=poison_candidates,
        )

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


@router.websocket("/ws/game")
async def game_socket(websocket: WebSocket) -> None:
    setup_result = setup_game()

    await manager.connect(websocket)
    logger.info(
        "websocket connected human_seat=%s active_connections=%s",
        setup_result.human_seat_id,
        manager.active_connections,
    )
    attach_context_bridge(
        setup_result.context,
        lambda payload: manager.send_json(websocket, payload),
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
    engine_task = asyncio.create_task(
        run_game_session(
            setup_result,
            lambda payload: manager.send_json(websocket, payload),
            close_connection=lambda: websocket.close(
                code=GAME_OVER_CLOSE_CODE,
                reason=GAME_OVER_CLOSE_REASON,
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
            resolve_human_submit_action(
                setup_result,
                envelope.data.model_dump(exclude_none=True),
            )
            await manager.send_json(
                websocket,
                build_system_message(f"ack:{action}"),
            )
    except WebSocketDisconnect:
        logger.info("websocket disconnected by client")
    finally:
        manager.disconnect(websocket)
        logger.info("websocket cleanup finished active_connections=%s", manager.active_connections)
        if not engine_task.done():
            engine_task.cancel()
