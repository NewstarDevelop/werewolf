from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.protocols.c2s import ClientEnvelope
from app.protocols.s2c import ServerEnvelope, SystemMessagePayload
from app.ws.manager import ConnectionManager

router = APIRouter()
manager = ConnectionManager()


def build_system_message(message: str) -> dict[str, object]:
    return ServerEnvelope(
        type="SYSTEM_MSG",
        data=SystemMessagePayload(message=message),
    ).model_dump()


@router.websocket("/ws/game")
async def game_socket(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    await manager.send_json(websocket, build_system_message("connected"))

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
