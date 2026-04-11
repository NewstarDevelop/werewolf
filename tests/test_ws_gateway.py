import asyncio
import random

from fastapi.testclient import TestClient

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.main import app
from app.services.setup_game import setup_game
from app.ws.routes import (
    WebSocketGameEngine,
    attach_context_bridge,
    run_game_session,
)


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


def test_websocket_acknowledges_submit_action(monkeypatch) -> None:
    async def idle_session(*args, **kwargs) -> None:
        await asyncio.sleep(0)

    monkeypatch.setattr("app.ws.routes.run_game_session", idle_session)
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


def test_run_game_session_emits_game_over_payload() -> None:
    sent_payloads: list[dict[str, object]] = []
    setup_result = setup_game(rng=random.Random(7))

    class StubEngine:
        async def run_loop(
            self,
            *,
            context: GameContext | None = None,
            max_rounds: int = 1,
        ) -> GameContext:
            assert context is not None
            for player in context.players.values():
                if player.role is Role.WOLF:
                    player.mark_dead()
            return context

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    asyncio.run(
        run_game_session(
            setup_result,
            send_json,
            engine=StubEngine(),  # type: ignore[arg-type]
            max_rounds=1,
        ),
    )

    assert sent_payloads == [
        {
            "type": "GAME_OVER",
            "data": {
                "winning_side": "GOOD",
                "summary": "狼人已全部出局，好人阵营获胜。",
                "revealed_roles": {
                    seat_id: player.role.value
                    for seat_id, player in sorted(setup_result.context.players.items())
                },
            },
            "meta": {},
        },
    ]


def test_websocket_game_engine_emits_ai_thinking_payload() -> None:
    sent_payloads: list[dict[str, object]] = []

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    async def run() -> None:
        engine = WebSocketGameEngine(send_json=send_json)
        await engine._notify_thinking(4, True)
        await engine._notify_thinking(4, False)

    asyncio.run(run())

    assert sent_payloads == [
        {
            "type": "AI_THINKING",
            "data": {
                "seat_id": 4,
                "is_thinking": True,
                "message": None,
            },
            "meta": {},
        },
        {
            "type": "AI_THINKING",
            "data": {
                "seat_id": 4,
                "is_thinking": False,
                "message": None,
            },
            "meta": {},
        },
    ]
