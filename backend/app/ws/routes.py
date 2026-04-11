from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

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


@router.websocket("/ws/game")
async def game_socket(websocket: WebSocket) -> None:
    setup_result = setup_game()

    await manager.connect(websocket)
    await manager.send_json(websocket, build_system_message("connected"))
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
