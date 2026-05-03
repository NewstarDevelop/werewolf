import asyncio

from fastapi import WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.ws.manager import ConnectionManager


class FakeWebSocket:
    def __init__(
        self,
        *,
        state: WebSocketState = WebSocketState.CONNECTED,
        send_error: Exception | None = None,
    ) -> None:
        self.application_state = state
        self.send_error = send_error
        self.sent_payloads: list[dict[str, object]] = []

    async def accept(self) -> None:
        return None

    async def send_json(self, payload: dict[str, object]) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.sent_payloads.append(payload)


def test_send_json_drops_socket_that_is_no_longer_connected() -> None:
    async def run() -> None:
        manager = ConnectionManager()
        websocket = FakeWebSocket(state=WebSocketState.DISCONNECTED)

        await manager.connect(websocket)
        await manager.send_json(websocket, {"type": "SYSTEM_MSG"})

        assert manager.active_connections == 0
        assert websocket.sent_payloads == []

    asyncio.run(run())

def test_send_json_drops_socket_after_send_disconnect() -> None:
    async def run() -> None:
        manager = ConnectionManager()
        websocket = FakeWebSocket(send_error=WebSocketDisconnect(code=1006))

        await manager.connect(websocket)
        await manager.send_json(websocket, {"type": "SYSTEM_MSG"})

        assert manager.active_connections == 0
        assert websocket.sent_payloads == []

    asyncio.run(run())
