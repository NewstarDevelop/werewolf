from fastapi.testclient import TestClient

from app.main import app


def test_websocket_sends_welcome_message() -> None:
    client = TestClient(app)

    with client.websocket_connect("/ws/game") as websocket:
        message = websocket.receive_json()

    assert message["type"] == "SYSTEM_MSG"
    assert message["data"]["message"] == "connected"


def test_websocket_acknowledges_submit_action() -> None:
    client = TestClient(app)

    with client.websocket_connect("/ws/game") as websocket:
        websocket.receive_json()
        websocket.send_json(
            {
                "type": "SUBMIT_ACTION",
                "data": {"action": "vote", "target": 3},
            }
        )
        message = websocket.receive_json()

    assert message["type"] == "SYSTEM_MSG"
    assert message["data"]["message"] == "ack:VOTE"
