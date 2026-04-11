import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.domain.game_context import GameContext
from app.domain.player import HumanPlayer
from app.engine.check_win import check_win
from app.engine.game_engine import GameEngine
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
SendJson = Callable[[dict[str, object]], Awaitable[None]]


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
    action_type: Literal["SPEAK", "VOTE", "WOLF_KILL", "SEER_CHECK", "WITCH_ACTION"],
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


class WebSocketGameEngine(GameEngine):
    def __init__(self, *, send_json: SendJson) -> None:
        super().__init__()
        self._send_json = send_json
        self._active_context: GameContext | None = None

    async def _notify_thinking(self, seat_id: int, is_thinking: bool) -> None:
        await self._send_json(build_ai_thinking_message(seat_id, is_thinking))

    async def _await_human_input(
        self,
        seat_id: int,
        *,
        action_type: Literal["SPEAK", "VOTE", "WOLF_KILL", "SEER_CHECK", "WITCH_ACTION"],
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
    engine: GameEngine | None = None,
    max_rounds: int = 20,
) -> None:
    active_engine = engine or WebSocketGameEngine(send_json=send_json)
    final_context = await active_engine.run_loop(
        context=setup_result.context,
        max_rounds=max_rounds,
    )
    game_over_payload = build_game_over_message(final_context)
    if game_over_payload is not None:
        await send_json(game_over_payload)


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
        ),
    )

    try:
        while True:
            raw_message = await websocket.receive_json()
            try:
                envelope = ClientEnvelope.model_validate(raw_message)
            except ValidationError:
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
        manager.disconnect(websocket)
    finally:
        if not engine_task.done():
            engine_task.cancel()
