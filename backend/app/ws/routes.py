import asyncio
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.domain.game_context import GameContext
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
            speaker="系统",
            visibility="private",
        ),
    ).model_dump()


def build_public_message(message: str) -> dict[str, object]:
    return ChatUpdateEnvelope(
        type="CHAT_UPDATE",
        data=ChatUpdatePayload(
            message=message,
            speaker="系统",
            visibility="public",
        ),
    ).model_dump()


def build_ai_thinking_message(seat_id: int, is_thinking: bool) -> dict[str, object]:
    return AIThinkingEnvelope(
        type="AI_THINKING",
        data=AIThinkingPayload(seat_id=seat_id, is_thinking=is_thinking),
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

    async def _notify_thinking(self, seat_id: int, is_thinking: bool) -> None:
        await self._send_json(build_ai_thinking_message(seat_id, is_thinking))


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
            await manager.send_json(
                websocket,
                build_system_message(f"ack:{action}"),
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    finally:
        if not engine_task.done():
            engine_task.cancel()
