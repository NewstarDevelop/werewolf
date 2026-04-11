import asyncio

from fastapi.testclient import TestClient

from app.domain.game_context import GameContext
from app.main import app
from app.ws.routes import attach_context_bridge


def test_websocket_sends_welcome_message() -> None:
    client = TestClient(app)

    with client.websocket_connect("/ws/game") as websocket:
        message = websocket.receive_json()
        public_message = websocket.receive_json()
        private_message = websocket.receive_json()

    assert message["type"] == "SYSTEM_MSG"
    assert message["data"]["message"] == "connected"
    assert public_message["type"] == "CHAT_UPDATE"
    assert public_message["data"]["visibility"] == "public"
    assert public_message["data"]["message"] == "游戏开始，分配身份完毕。"
    assert private_message["type"] == "CHAT_UPDATE"
    assert private_message["data"]["visibility"] == "private"
    assert "身份是" in private_message["data"]["message"]


def test_websocket_acknowledges_submit_action() -> None:
    client = TestClient(app)

    with client.websocket_connect("/ws/game") as websocket:
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json(
            {
                "type": "SUBMIT_ACTION",
                "data": {"action_type": "VOTE", "target": 3},
            }
        )
        message = websocket.receive_json()

    assert message["type"] == "SYSTEM_MSG"
    assert message["data"]["message"] == "ack:VOTE"


def test_attach_context_bridge_forwards_public_and_private_messages() -> None:
    forwarded_payloads: list[dict[str, object]] = []
    context = GameContext()

    async def send_json(payload: dict[str, object]) -> None:
        forwarded_payloads.append(payload)

    async def run() -> None:
        attach_context_bridge(context, send_json)
        context.add_public_message("天黑请闭眼。")
        context.add_private_message(3, "你的身份是女巫。")
        await asyncio.sleep(0)

    asyncio.run(run())

    assert forwarded_payloads == [
        {
            "type": "CHAT_UPDATE",
            "data": {
                "message": "天黑请闭眼。",
                "seat_id": None,
                "speaker": "系统",
                "visibility": "public",
            },
            "meta": {},
        },
        {
            "type": "CHAT_UPDATE",
            "data": {
                "message": "你的身份是女巫。",
                "seat_id": 3,
                "speaker": "系统",
                "visibility": "private",
            },
            "meta": {},
        },
    ]
