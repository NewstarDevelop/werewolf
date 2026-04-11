import asyncio
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.domain.game_context import GameContext
from app.protocols.c2s import ClientEnvelope
from app.protocols.s2c import (
    ChatUpdateEnvelope,
    ChatUpdatePayload,
    SystemMessageEnvelope,
    SystemMessagePayload,
)
from app.services.setup_game import setup_game
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


def attach_context_bridge(context: GameContext, send_json: SendJson) -> None:
    loop = asyncio.get_running_loop()

    context.on_public_message(
        lambda message: loop.create_task(send_json(build_public_message(message))),
    )
    context.on_private_message(
        lambda seat_id, message: loop.create_task(send_json(build_private_message(message, seat_id))),
    )


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
