import asyncio
import random

from fastapi.testclient import TestClient

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer, HumanPlayer
from app.main import app
from app.services.setup_game import setup_game
from app.engine.night.witch_action import WitchResources
from app.ws.routes import (
    WebSocketGameEngine,
    attach_context_bridge,
    resolve_human_submit_action,
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
    assert public_message["data"]["message"] == "\u6e38\u620f\u5f00\u59cb\uff0c\u5206\u914d\u8eab\u4efd\u5b8c\u6bd5\u3002"
    assert private_message["type"] == "CHAT_UPDATE"
    assert private_message["data"]["visibility"] == "private"
    assert "\u8eab\u4efd\u662f" in private_message["data"]["message"]


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
        context.add_public_message("\u5929\u9ed1\u8bf7\u95ed\u773c\u3002")
        context.add_private_message(3, "\u4f60\u7684\u8eab\u4efd\u662f\u5973\u5deb\u3002")
        await asyncio.sleep(0)

    asyncio.run(run())

    assert forwarded_payloads == [
        {
            "type": "CHAT_UPDATE",
            "data": {
                "message": "\u5929\u9ed1\u8bf7\u95ed\u773c\u3002",
                "seat_id": None,
                "speaker": "\u7cfb\u7edf",
                "visibility": "public",
            },
            "meta": {},
        },
        {
            "type": "CHAT_UPDATE",
            "data": {
                "message": "\u4f60\u7684\u8eab\u4efd\u662f\u5973\u5deb\u3002",
                "seat_id": 3,
                "speaker": "\u7cfb\u7edf",
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
                "summary": "\u72fc\u4eba\u5df2\u5168\u90e8\u51fa\u5c40\uff0c\u597d\u4eba\u9635\u8425\u83b7\u80dc\u3002",
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


def test_websocket_game_engine_uses_default_llm_client_for_ai_speech() -> None:
    sent_payloads: list[dict[str, object]] = []
    context = GameContext()
    context.add_player(AIPlayer(seat_id=2, role=Role.SEER, personality="谨慎分析"))
    context.add_player(HumanPlayer(seat_id=1, role=Role.VILLAGER))
    context.add_player(HumanPlayer(seat_id=3, role=Role.WOLF))

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    engine = WebSocketGameEngine(send_json=send_json)
    speech = asyncio.run(engine._llm_speaker(context, 2))

    assert speech
    assert "听" in speech


def test_websocket_game_engine_run_loop_emits_local_llm_speech() -> None:
    sent_payloads: list[dict[str, object]] = []
    context = GameContext()
    context.add_player(AIPlayer(seat_id=1, role=Role.WOLF, personality="强势带队"))
    context.add_player(AIPlayer(seat_id=2, role=Role.VILLAGER, personality="沉默观察"))
    context.add_player(AIPlayer(seat_id=3, role=Role.SEER, personality="谨慎分析"))
    context.add_player(AIPlayer(seat_id=4, role=Role.WITCH, personality="稳健分析"))
    context.add_player(AIPlayer(seat_id=5, role=Role.VILLAGER, personality="冷静拆点"))

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    async def run() -> None:
        attach_context_bridge(context, send_json)
        engine = WebSocketGameEngine(send_json=send_json)
        await engine.run_loop(context=context, max_rounds=1)

    asyncio.run(run())

    public_messages = [
        payload["data"]["message"]
        for payload in sent_payloads
        if payload["type"] == "CHAT_UPDATE" and payload["data"]["visibility"] == "public"
    ]

    assert any("信息还不够，我先听后置位怎么聊。" in message for message in public_messages)


def test_websocket_game_engine_requests_and_consumes_human_speech() -> None:
    sent_payloads: list[dict[str, object]] = []
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.SEER))

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    engine = WebSocketGameEngine(send_json=send_json)

    async def run_with_context() -> None:
        engine._active_context = context
        try:
            task = asyncio.create_task(engine._human_speaker(1))
            await asyncio.sleep(0)
            context.players[1].resolve_input({"action_type": "SPEAK", "text": "\u6211\u662f\u9884\u8a00\u5bb6\u3002"})
            result = await task
            assert result == "\u6211\u662f\u9884\u8a00\u5bb6\u3002"
        finally:
            engine._active_context = None

    asyncio.run(run_with_context())

    assert sent_payloads == [
        {
            "type": "REQUIRE_INPUT",
            "data": {
                "action_type": "SPEAK",
                "prompt": "\u8f6e\u5230\u4f60\u53d1\u8a00\uff0c\u8bf7\u4ee5 1 \u53f7\u73a9\u5bb6\u8eab\u4efd\u53d1\u8a00\u3002",
                "allowed_targets": [],
            },
            "meta": {},
        },
    ]


def test_resolve_human_submit_action_unlocks_pending_input() -> None:
    setup_result = setup_game(rng=random.Random(7))
    player = setup_result.context.players[setup_result.human_seat_id]
    assert isinstance(player, HumanPlayer)

    async def run() -> None:
        pending = player.begin_input()
        resolved = resolve_human_submit_action(
            setup_result,
            {"action_type": "SPEAK", "text": "\u8fc7\u3002"},
        )

        assert resolved is True
        assert await pending == {"action_type": "SPEAK", "text": "\u8fc7\u3002"}

    asyncio.run(run())


def test_websocket_game_engine_requests_and_consumes_human_vote() -> None:
    sent_payloads: list[dict[str, object]] = []
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.SEER))

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    engine = WebSocketGameEngine(send_json=send_json)

    async def run_with_context() -> None:
        engine._active_context = context
        try:
            task = asyncio.create_task(engine._human_vote(1, allowed_targets=[2, 3, 4]))
            await asyncio.sleep(0)
            context.players[1].resolve_input({"action_type": "VOTE", "target": 3})
            result = await task
            assert result == 3
        finally:
            engine._active_context = None

    asyncio.run(run_with_context())

    assert sent_payloads == [
        {
            "type": "REQUIRE_INPUT",
            "data": {
                "action_type": "VOTE",
                "prompt": "\u8bf7\u9009\u62e9\u4e00\u540d\u5b58\u6d3b\u73a9\u5bb6\u4f5c\u4e3a\u653e\u9010\u76ee\u6807\u3002",
                "allowed_targets": [2, 3, 4],
            },
            "meta": {},
        },
    ]


def test_websocket_game_engine_accepts_pass_for_human_vote() -> None:
    sent_payloads: list[dict[str, object]] = []
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.SEER))

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    engine = WebSocketGameEngine(send_json=send_json)

    async def run_with_context() -> None:
        engine._active_context = context
        try:
            task = asyncio.create_task(engine._human_vote(1, allowed_targets=[2, 3, 4]))
            await asyncio.sleep(0)
            context.players[1].resolve_input({"action_type": "PASS"})
            result = await task
            assert result is None
        finally:
            engine._active_context = None

    asyncio.run(run_with_context())

    assert sent_payloads == [
        {
            "type": "REQUIRE_INPUT",
            "data": {
                "action_type": "VOTE",
                "prompt": "\u8bf7\u9009\u62e9\u4e00\u540d\u5b58\u6d3b\u73a9\u5bb6\u4f5c\u4e3a\u653e\u9010\u76ee\u6807\u3002",
                "allowed_targets": [2, 3, 4],
            },
            "meta": {},
        },
    ]


def test_websocket_game_engine_requests_and_consumes_human_wolf_target() -> None:
    sent_payloads: list[dict[str, object]] = []
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.WOLF))
    context.add_player(HumanPlayer(seat_id=2, role=Role.SEER))
    context.add_player(HumanPlayer(seat_id=3, role=Role.VILLAGER))

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    engine = WebSocketGameEngine(send_json=send_json)

    async def run_with_context() -> None:
        engine._active_context = context
        try:
            target_task = asyncio.create_task(engine._select_wolf_target(context))
            await asyncio.sleep(0)
            context.players[1].resolve_input({"action_type": "WOLF_KILL", "target": 3})
            result = await target_task
            assert result == 3
        finally:
            engine._active_context = None

    asyncio.run(run_with_context())

    assert sent_payloads == [
        {
            "type": "REQUIRE_INPUT",
            "data": {
                "action_type": "WOLF_KILL",
                "prompt": "\u8bf7\u9009\u62e9\u4eca\u591c\u8981\u51fb\u6740\u7684\u5b58\u6d3b\u73a9\u5bb6\u3002",
                "allowed_targets": [2, 3],
            },
            "meta": {},
        },
    ]


def test_websocket_game_engine_requests_and_consumes_human_seer_target() -> None:
    sent_payloads: list[dict[str, object]] = []
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.SEER))
    context.add_player(HumanPlayer(seat_id=2, role=Role.WOLF))
    context.add_player(HumanPlayer(seat_id=3, role=Role.VILLAGER))

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    engine = WebSocketGameEngine(send_json=send_json)

    async def run_with_context() -> None:
        engine._active_context = context
        try:
            target_task = asyncio.create_task(
                engine._select_seer_target(
                    context,
                    seer_seat=1,
                    allowed_targets=[2, 3],
                )
            )
            await asyncio.sleep(0)
            context.players[1].resolve_input({"action_type": "SEER_CHECK", "target": 2})
            result = await target_task
            assert result == 2
        finally:
            engine._active_context = None

    asyncio.run(run_with_context())

    assert sent_payloads == [
        {
            "type": "REQUIRE_INPUT",
            "data": {
                "action_type": "SEER_CHECK",
                "prompt": "\u8bf7\u9009\u62e9\u4eca\u591c\u8981\u67e5\u9a8c\u7684\u5b58\u6d3b\u73a9\u5bb6\u3002",
                "allowed_targets": [2, 3],
            },
            "meta": {},
        },
    ]


def test_websocket_game_engine_requests_and_consumes_human_witch_action() -> None:
    sent_payloads: list[dict[str, object]] = []
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.WITCH))
    context.add_player(HumanPlayer(seat_id=2, role=Role.WOLF))
    context.add_player(HumanPlayer(seat_id=3, role=Role.VILLAGER))
    context.add_player(HumanPlayer(seat_id=4, role=Role.SEER))

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    engine = WebSocketGameEngine(send_json=send_json)

    async def run_with_context() -> None:
        engine._active_context = context
        try:
            action_task = asyncio.create_task(
                engine._select_witch_action(
                    context,
                    witch_seat=1,
                    resources=engine._witch_resources.setdefault(1, WitchResources()),
                    save_candidates=[3],
                    poison_candidates=[2, 4],
                )
            )
            await asyncio.sleep(0)
            context.players[1].resolve_input({"action_type": "WITCH_POISON", "target": 2})
            result = await action_task
            assert result == (None, 2)
        finally:
            engine._active_context = None

    asyncio.run(run_with_context())

    assert sent_payloads == [
        {
            "type": "REQUIRE_INPUT",
            "data": {
                "action_type": "WITCH_ACTION",
                "prompt": "\u6628\u591c 3 \u53f7\u88ab\u51fb\u6740\uff0c\u4f60\u53ef\u4ee5\u9009\u62e9\u6551\u4eba\u3002 \u4f60\u4e5f\u53ef\u4ee5\u9009\u62e9\u6bd2\u4eba\u6216\u8df3\u8fc7\u3002",
                "allowed_targets": [2, 4],
            },
            "meta": {},
        },
    ]


def test_websocket_game_engine_requests_and_consumes_human_hunter_target() -> None:
    sent_payloads: list[dict[str, object]] = []
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.HUNTER, is_alive=False))
    context.add_player(HumanPlayer(seat_id=2, role=Role.WOLF))
    context.add_player(HumanPlayer(seat_id=3, role=Role.VILLAGER))

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    engine = WebSocketGameEngine(send_json=send_json)

    async def run_with_context() -> None:
        engine._active_context = context
        try:
            target_task = asyncio.create_task(engine._select_hunter_target(context, hunter_seat=1))
            await asyncio.sleep(0)
            context.players[1].resolve_input({"action_type": "HUNTER_SHOOT", "target": 2})
            result = await target_task
            assert result == 2
        finally:
            engine._active_context = None

    asyncio.run(run_with_context())

    assert sent_payloads == [
        {
            "type": "REQUIRE_INPUT",
            "data": {
                "action_type": "HUNTER_SHOOT",
                "prompt": "\u4f60\u53ef\u4ee5\u9009\u62e9\u4e00\u540d\u5b58\u6d3b\u73a9\u5bb6\u5f00\u67aa\u3002",
                "allowed_targets": [2, 3],
            },
            "meta": {},
        },
    ]
