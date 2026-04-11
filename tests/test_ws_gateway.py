from fastapi.testclient import TestClient

from app.main import app


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
