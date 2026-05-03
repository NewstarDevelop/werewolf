from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    @property
    def active_connections(self) -> int:
        return len(self._connections)

    async def send_json(self, websocket: WebSocket, payload: dict[str, object]) -> None:
        if websocket.application_state != WebSocketState.CONNECTED:
            self.disconnect(websocket)
            return
        try:
            await websocket.send_json(payload)
        except (RuntimeError, WebSocketDisconnect, OSError):
            self.disconnect(websocket)
            return
