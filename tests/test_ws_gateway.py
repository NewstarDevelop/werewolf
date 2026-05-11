import asyncio
import logging
import random
import threading

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.domain.enums import Role
from app.domain.game_context import (
    GameContext,
    NightActionSnapshot,
    PrivateChatEvent,
    PublicChatEvent,
    VoteSnapshot,
)
from app.domain.view_mask import build_player_view
from app.domain.player import AIPlayer, HumanPlayer
from app.main import app
from app.services.setup_game import GameSetupResult, setup_game
from app.engine.day.day_speaking import run_day_speaking
from app.engine.night.witch_action import WitchResources
from app.engine.states.phase import GamePhase
from app.ws.routes import (
    WebSocketGameEngine,
    allowed_submit_action_types,
    attach_context_bridge,
    build_death_revealed_message,
    build_game_over_message,
    build_phase_changed_message,
    build_private_chat_event_message,
    build_player_state_patch_message,
    build_public_chat_event_message,
    build_settlement_recap,
    build_vote_resolved_message,
    GAME_OVER_CLOSE_CODE,
    known_role_seat_ids_from_setup,
    log_game_session_task_outcome,
    parse_ai_delay_seconds,
    resolve_human_submit_action,
    run_game_session,
)


def test_websocket_sends_welcome_message() -> None:
    client = TestClient(app)

    with client.websocket_connect("/ws/game") as websocket:
        message = websocket.receive_json()
        public_message = websocket.receive_json()
        private_message = websocket.receive_json()
        player_patch = websocket.receive_json()
        phase_changed = websocket.receive_json()

    assert message["type"] == "SYSTEM_MSG"
    assert message["data"]["message"] == "connected"
    assert public_message["type"] == "CHAT_UPDATE"
    assert public_message["data"]["visibility"] == "public"
    assert public_message["data"]["message"] == "\u6e38\u620f\u5f00\u59cb\uff0c\u5206\u914d\u8eab\u4efd\u5b8c\u6bd5\u3002"
    assert private_message["type"] == "CHAT_UPDATE"
    assert private_message["data"]["visibility"] == "private"
    assert "\u8eab\u4efd\u662f" in private_message["data"]["message"]
    assert player_patch["type"] == "PLAYER_STATE_PATCH"
    human_patches = [
        player
        for player in player_patch["data"]["players"]
        if player["is_human"] is True
    ]
    assert len(human_patches) == 1
    assert human_patches[0]["role_code"] in {
        role.value for role in Role
    }
    assert phase_changed == {
        "type": "PHASE_CHANGED",
        "data": {
            "phase": "INIT",
            "day_count": 1,
        },
        "meta": {},
    }


def test_parse_ai_delay_seconds_clamps_invalid_and_large_values() -> None:
    assert parse_ai_delay_seconds(None) == 0.0
    assert parse_ai_delay_seconds("bad") == 0.0
    assert parse_ai_delay_seconds("-50") == 0.0
    assert parse_ai_delay_seconds("700") == 0.7
    assert parse_ai_delay_seconds("9999") == 2.0


def test_websocket_acknowledges_submit_action(monkeypatch) -> None:
    ready = threading.Event()

    async def pending_vote_session(setup_result, *args, **kwargs) -> None:
        player = setup_result.context.players[setup_result.human_seat_id]
        assert isinstance(player, HumanPlayer)
        pending = player.begin_input(
            allowed_action_types={"VOTE", "PASS"},
            allowed_targets={3},
            request_id="input-1",
        )
        ready.set()
        try:
            await pending
        finally:
            player.clear_input()

    monkeypatch.setattr("app.ws.routes.run_game_session", pending_vote_session)
    client = TestClient(app)

    with client.websocket_connect("/ws/game") as websocket:
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()
        assert ready.wait(timeout=1)
        websocket.send_json(
            {
                "type": "SUBMIT_ACTION",
                "data": {"action_type": "VOTE", "target": 3, "request_id": "input-1"},
            }
        )
        message = websocket.receive_json()

    assert message["type"] == "SYSTEM_MSG"
    assert message["data"]["message"] == "ack:VOTE"
    assert message["meta"]["request_id"] == "input-1"


def test_websocket_rejects_submit_action_without_pending_input(monkeypatch, caplog) -> None:
    async def idle_session(*args, **kwargs) -> None:
        await asyncio.sleep(0)

    monkeypatch.setattr("app.ws.routes.run_game_session", idle_session)
    caplog.set_level(logging.WARNING, logger="app.ws.routes")
    client = TestClient(app)

    with client.websocket_connect("/ws/game") as websocket:
        websocket.receive_json()
        websocket.receive_json()
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
    assert message["data"]["message"] == "reject:VOTE"
    assert "unexpected websocket action ignored action=VOTE" in caplog.text


def test_websocket_logs_invalid_payload_warning(monkeypatch, caplog) -> None:
    async def idle_session(*args, **kwargs) -> None:
        await asyncio.sleep(0)

    monkeypatch.setattr("app.ws.routes.run_game_session", idle_session)
    caplog.set_level(logging.WARNING, logger="app.ws.routes")
    client = TestClient(app)

    with client.websocket_connect("/ws/game") as websocket:
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json({"type": "BROKEN"})
        message = websocket.receive_json()

    assert message["type"] == "SYSTEM_MSG"
    assert message["data"]["message"] == "invalid payload"
    assert "invalid websocket payload received" in caplog.text


def test_websocket_closes_after_game_over(monkeypatch) -> None:
    async def terminal_session(setup_result, send_json, *, close_connection=None, **kwargs) -> None:
        await send_json(
            {
                "type": "GAME_OVER",
                "data": {
                    "winning_side": "GOOD",
                    "summary": "好人阵营获胜。",
                    "revealed_roles": {},
                },
                "meta": {},
            }
        )
        assert close_connection is not None
        await close_connection()

    monkeypatch.setattr("app.ws.routes.run_game_session", terminal_session)
    client = TestClient(app)

    with client.websocket_connect("/ws/game") as websocket:
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()

        game_over = websocket.receive_json()
        assert game_over["type"] == "GAME_OVER"

        try:
            websocket.receive_json()
        except WebSocketDisconnect as exc:
            assert exc.code == GAME_OVER_CLOSE_CODE
        else:
            raise AssertionError("expected websocket to close after GAME_OVER")


def test_attach_context_bridge_forwards_public_and_private_messages() -> None:
    forwarded_payloads: list[dict[str, object]] = []
    context = GameContext()

    async def send_json(payload: dict[str, object]) -> None:
        forwarded_payloads.append(payload)

    async def run() -> None:
        attach_context_bridge(context, send_json, viewer_seat_id=3)
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


def test_attach_context_bridge_filters_private_messages_for_other_seats() -> None:
    forwarded_payloads: list[dict[str, object]] = []
    context = GameContext()

    async def send_json(payload: dict[str, object]) -> None:
        forwarded_payloads.append(payload)

    async def run() -> None:
        attach_context_bridge(context, send_json, viewer_seat_id=1)
        context.add_private_message(3, "\u72fc\u4eba\u5df2\u9009\u62e9\u76ee\u6807\u3002")
        await asyncio.sleep(0)

    asyncio.run(run())

    assert forwarded_payloads == []


def test_private_chat_event_message_carries_night_feedback_metadata() -> None:
    payload = build_private_chat_event_message(
        PrivateChatEvent(
            seat_id=3,
            message="你选择今晚击杀 5 号。",
            event_type="NIGHT_ACTION_FEEDBACK",
            target_seats=[5],
        )
    )

    assert payload == {
        "type": "CHAT_UPDATE",
        "data": {
            "message": "你选择今晚击杀 5 号。",
            "seat_id": 3,
            "speaker": "\u7cfb\u7edf",
            "visibility": "private",
        },
        "meta": {
            "event_type": "NIGHT_ACTION_FEEDBACK",
            "target_seats": [5],
        },
    }


def test_attach_context_bridge_forwards_private_night_feedback_metadata() -> None:
    forwarded_payloads: list[dict[str, object]] = []
    context = GameContext()

    async def send_json(payload: dict[str, object]) -> None:
        forwarded_payloads.append(payload)

    async def run() -> None:
        attach_context_bridge(context, send_json, viewer_seat_id=1)
        context.add_private_message(
            1,
            "你选择查验 4 号。",
            event_type="NIGHT_ACTION_FEEDBACK",
            target_seats=[4],
        )
        await asyncio.sleep(0)

    asyncio.run(run())

    assert forwarded_payloads[0]["meta"] == {
        "event_type": "NIGHT_ACTION_FEEDBACK",
        "target_seats": [4],
    }


def test_day_speaking_publishes_human_speech_before_next_ai_speaker() -> None:
    forwarded_payloads: list[dict[str, object]] = []
    messages_seen_before_ai_speech: list[str] = []
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.SEER))
    context.add_player(AIPlayer(seat_id=2, role=Role.WOLF, personality="steady"))

    async def send_json(payload: dict[str, object]) -> None:
        forwarded_payloads.append(payload)

    async def human_speaker(seat_id: int) -> str:
        assert seat_id == 1
        return "我是预言家。"

    async def ai_speaker(seat_id: int) -> str:
        assert seat_id == 2
        messages_seen_before_ai_speech.extend(
            str(payload["data"]["message"])
            for payload in forwarded_payloads
            if payload["type"] == "CHAT_UPDATE"
        )
        return "我听到了前置位发言。"

    async def notify_thinking(_: int, __: bool) -> None:
        return None

    async def run() -> None:
        attach_context_bridge(context, send_json, viewer_seat_id=1)
        await run_day_speaking(
            context,
            start_seat=1,
            human_speaker=human_speaker,
            ai_speaker=ai_speaker,
            notify_thinking=notify_thinking,
        )

    asyncio.run(run())

    assert messages_seen_before_ai_speech == ["1号发言：我是预言家。"]


def test_log_game_session_task_outcome_records_failures(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="app.ws.routes")

    async def boom() -> None:
        raise RuntimeError("boom")

    async def run() -> None:
        task = asyncio.create_task(boom())
        task.add_done_callback(log_game_session_task_outcome)
        await asyncio.sleep(0)

    asyncio.run(run())

    assert "game session task failed" in caplog.text


def test_run_game_session_emits_game_over_payload() -> None:
    sent_payloads: list[dict[str, object]] = []
    closed = False
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

    async def close_connection() -> None:
        nonlocal closed
        closed = True

    asyncio.run(
        run_game_session(
            setup_result,
            send_json,
            close_connection=close_connection,
            engine=StubEngine(),  # type: ignore[arg-type]
            max_rounds=1,
        ),
    )

    assert sent_payloads[0]["type"] == "GAME_OVER"
    assert sent_payloads[0]["data"]["winning_side"] == "GOOD"
    assert sent_payloads[0]["data"]["summary"] == "狼人已全部出局，好人阵营获胜。"
    assert sent_payloads[0]["data"]["revealed_roles"] == {
        seat_id: player.role.value
        for seat_id, player in sorted(setup_result.context.players.items())
    }
    assert sent_payloads[0]["data"]["recap"]["players"][0]["seat_id"] == 1
    assert closed is True


def test_build_game_over_message_handles_safety_stop_draw() -> None:
    context = GameContext(phase=GamePhase.GAME_OVER.value)
    context.add_player(HumanPlayer(seat_id=1, role=Role.WOLF))
    context.add_player(AIPlayer(seat_id=2, role=Role.VILLAGER, personality="steady"))
    context.add_player(AIPlayer(seat_id=3, role=Role.SEER, personality="quiet"))
    context.add_public_message("夜尽未分胜负，本局暂止。")

    payload = build_game_over_message(context)

    assert payload == {
        "type": "GAME_OVER",
        "data": {
            "winning_side": "DRAW",
            "summary": "夜尽未分胜负，本局暂止。",
            "revealed_roles": {
                1: "WOLF",
                2: "VILLAGER",
                3: "SEER",
            },
            "recap": {
                "day_count": 1,
                "outcome_reason": "达到回合上限仍未分出胜负，系统安全停局。",
                "role_reveal_summary": "狼人：1号；神职：3号；平民：2号。",
                "players": [
                    {
                        "seat_id": 1,
                        "role_code": "WOLF",
                        "side": "WOLF",
                        "is_alive": True,
                        "is_human": True,
                    },
                    {
                        "seat_id": 2,
                        "role_code": "VILLAGER",
                        "side": "GOOD",
                        "is_alive": True,
                        "is_human": False,
                    },
                    {
                        "seat_id": 3,
                        "role_code": "SEER",
                        "side": "GOOD",
                        "is_alive": True,
                        "is_human": False,
                    },
                ],
                "nights": [],
                "days": [],
                "key_events": [],
                "timeline": [
                    {
                        "day_count": 1,
                        "phase": "GAME_OVER",
                        "event_type": "PUBLIC_MESSAGE",
                        "message": "夜尽未分胜负，本局暂止。",
                        "actor_seat": None,
                        "target_seats": [],
                    },
                ],
                "final_vote": None,
            },
        },
        "meta": {},
    }


def test_build_settlement_recap_includes_roles_events_and_final_vote() -> None:
    context = GameContext(phase=GamePhase.DAY_START.value, day_count=2)
    context.add_player(HumanPlayer(seat_id=1, role=Role.SEER))
    context.add_player(AIPlayer(seat_id=2, role=Role.WOLF, personality="steady"))
    context.add_player(AIPlayer(seat_id=3, role=Role.VILLAGER, personality="quiet"))
    context.players[2].mark_dead()
    context.add_public_message(
        "天亮了。昨夜死亡的是 3号。",
        event_type="NIGHT_DEATH",
        target_seats=[3],
    )
    context.add_public_message(
        "1号发言：我查杀2号。",
        message_kind="speech",
        event_type="SPEECH",
        actor_seat=1,
    )
    context.night_actions.append(
        NightActionSnapshot(
            day_count=2,
            wolf_target=3,
            seer_seat=1,
            seer_target=2,
            seer_result="WOLF",
            witch_seat=3,
            witch_save_target=3,
            dead_seats=[],
        )
    )
    context.last_vote_result = VoteSnapshot(
        day_count=2,
        votes={2: 2},
        ballots={1: 2, 3: 2},
        abstentions=[],
        banished_seat=2,
        summary="2号玩家被放逐出局。",
    )
    context.vote_history.append(context.last_vote_result)

    recap = build_settlement_recap(context).model_dump()

    assert recap["day_count"] == 2
    assert recap["outcome_reason"] == "狼人全灭。"
    assert recap["role_reveal_summary"] == "狼人：2号；神职：1号；平民：3号。"
    assert recap["players"] == [
        {
            "seat_id": 1,
            "role_code": "SEER",
            "side": "GOOD",
            "is_alive": True,
            "is_human": True,
        },
        {
            "seat_id": 2,
            "role_code": "WOLF",
            "side": "WOLF",
            "is_alive": False,
            "is_human": False,
        },
        {
            "seat_id": 3,
            "role_code": "VILLAGER",
            "side": "GOOD",
            "is_alive": True,
            "is_human": False,
        },
    ]
    assert recap["nights"] == [
        {
            "day_count": 2,
            "wolf_target": 3,
            "seer_seat": 1,
            "seer_target": 2,
            "seer_result": "WOLF",
            "witch_seat": 3,
            "witch_save_target": 3,
            "witch_poison_target": None,
            "dead_seats": [],
        }
    ]
    assert recap["days"][0]["speeches"][0]["message"] == "1号发言：我查杀2号。"
    assert recap["days"][0]["vote_explanation"] == "2号以 2 票成为最高票，被放逐出局。"
    assert recap["key_events"][0]["event_type"] == "NIGHT_DEATH"
    assert recap["key_events"][0]["phase"] == "DAY_START"
    assert [event["event_type"] for event in recap["timeline"]] == [
        "NIGHT_DEATH",
        "SPEECH",
    ]
    assert recap["final_vote"]["summary"] == "2号玩家被放逐出局。"


def test_run_game_session_emits_draw_payload_on_safety_stop() -> None:
    sent_payloads: list[dict[str, object]] = []
    closed = False
    setup_result = setup_game(rng=random.Random(7))

    class DrawEngine:
        async def run_loop(
            self,
            *,
            context: GameContext | None = None,
            max_rounds: int = 1,
        ) -> GameContext:
            assert context is not None
            context.phase = GamePhase.GAME_OVER.value
            context.add_public_message("夜尽未分胜负，本局暂止。")
            return context

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    async def close_connection() -> None:
        nonlocal closed
        closed = True

    asyncio.run(
        run_game_session(
            setup_result,
            send_json,
            close_connection=close_connection,
            engine=DrawEngine(),  # type: ignore[arg-type]
            max_rounds=1,
        ),
    )

    assert sent_payloads[0]["data"]["winning_side"] == "DRAW"
    assert sent_payloads[0]["data"]["summary"] == "夜尽未分胜负，本局暂止。"
    assert closed is True


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


def test_websocket_game_engine_disables_human_speech_timeout() -> None:
    engine = WebSocketGameEngine(send_json=lambda _: asyncio.sleep(0))

    assert engine._human_speech_timeout_seconds is None


def test_build_player_state_patch_message_hides_roles_by_default() -> None:
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.WITCH, is_alive=False))

    payload = build_player_state_patch_message(context, [1])

    assert payload == {
        "type": "PLAYER_STATE_PATCH",
        "data": {
            "players": [
                {
                    "seat_id": 1,
                    "is_alive": False,
                    "is_human": True,
                    "role_code": None,
                    "is_thinking": False,
                }
            ],
        },
        "meta": {},
    }


def test_build_player_state_patch_message_can_reveal_roles() -> None:
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.WITCH))

    payload = build_player_state_patch_message(context, [1], reveal_roles=True)

    assert payload["data"]["players"][0]["role_code"] == "WITCH"


def test_build_player_state_patch_message_can_reveal_selected_roles() -> None:
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.WOLF))
    context.add_player(AIPlayer(seat_id=2, role=Role.WOLF, personality="steady"))
    context.add_player(AIPlayer(seat_id=3, role=Role.SEER, personality="careful"))

    payload = build_player_state_patch_message(
        context,
        [1, 2, 3],
        reveal_role_seats={1, 2},
    )

    players = payload["data"]["players"]
    assert [player["role_code"] for player in players] == ["WOLF", "WOLF", None]


def test_known_role_seat_ids_include_wolf_teammates_for_wolf_view() -> None:
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.WOLF))
    context.add_player(AIPlayer(seat_id=2, role=Role.WOLF, personality="steady"))
    context.add_player(AIPlayer(seat_id=3, role=Role.SEER, personality="careful"))
    setup_result = GameSetupResult(
        context=context,
        human_seat_id=1,
        human_role=Role.WOLF.value,
        human_view=build_player_view(context, 1),
    )

    assert known_role_seat_ids_from_setup(setup_result) == [1, 2]


def test_websocket_welcome_reveals_wolf_teammates(monkeypatch) -> None:
    async def idle_session(*args, **kwargs) -> None:
        await asyncio.sleep(0)

    context = GameContext(phase="INIT")
    context.add_public_message("游戏开始，分配身份完毕。")
    context.add_player(AIPlayer(seat_id=1, role=Role.SEER, personality="careful"))
    context.add_player(AIPlayer(seat_id=2, role=Role.WOLF, personality="steady"))
    context.add_player(HumanPlayer(seat_id=7, role=Role.WOLF))
    context.add_private_message(7, "你的座位号是 7 号，身份是 WOLF。")
    setup_result = GameSetupResult(
        context=context,
        human_seat_id=7,
        human_role=Role.WOLF.value,
        human_view=build_player_view(context, 7),
    )

    monkeypatch.setattr("app.ws.routes.setup_game", lambda: setup_result)
    monkeypatch.setattr("app.ws.routes.run_game_session", idle_session)

    client = TestClient(app)
    with client.websocket_connect("/ws/game") as websocket:
        websocket.receive_json()
        websocket.receive_json()
        websocket.receive_json()
        player_patch = websocket.receive_json()

    players = player_patch["data"]["players"]
    assert [(player["seat_id"], player["role_code"]) for player in players] == [
        (2, "WOLF"),
        (7, "WOLF"),
    ]
    assert [player["is_human"] for player in players] == [False, True]


def test_public_chat_event_message_carries_structured_metadata() -> None:
    payload = build_public_chat_event_message(
        PublicChatEvent(
            message="3号发言：我站边预言家。",
            message_kind="speech",
            event_type="SPEECH",
            actor_seat=3,
        )
    )

    assert payload["type"] == "CHAT_UPDATE"
    assert payload["meta"] == {
        "message_kind": "speech",
        "event_type": "SPEECH",
        "actor_seat": 3,
    }


def test_attach_context_bridge_forwards_structured_death_metadata() -> None:
    forwarded_payloads: list[dict[str, object]] = []
    context = GameContext()

    async def send_json(payload: dict[str, object]) -> None:
        forwarded_payloads.append(payload)

    async def run() -> None:
        attach_context_bridge(context, send_json, viewer_seat_id=1)
        context.add_public_message(
            "2号玩家被放逐出局。",
            event_type="BANISHMENT",
            target_seats=[2],
        )
        await asyncio.sleep(0)

    asyncio.run(run())

    assert forwarded_payloads[0]["meta"] == {
        "event_type": "BANISHMENT",
        "target_seats": [2],
    }


def test_build_phase_changed_message_uses_context_phase_and_day() -> None:
    context = GameContext(phase="DAY_SPEAKING", day_count=2)

    payload = build_phase_changed_message(context)

    assert payload == {
        "type": "PHASE_CHANGED",
        "data": {
            "phase": "DAY_SPEAKING",
            "day_count": 2,
        },
        "meta": {},
    }


def test_websocket_game_engine_emits_phase_changed_payload() -> None:
    sent_payloads: list[dict[str, object]] = []
    context = GameContext(phase="NIGHT_START", day_count=1)

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    async def run() -> None:
        engine = WebSocketGameEngine(send_json=send_json)
        await engine._notify_phase_changed(context)

    asyncio.run(run())

    assert sent_payloads == [
        {
            "type": "PHASE_CHANGED",
            "data": {
                "phase": "NIGHT_START",
                "day_count": 1,
            },
            "meta": {},
        }
    ]


def test_build_death_revealed_message_uses_context_day() -> None:
    context = GameContext(day_count=1)

    payload = build_death_revealed_message(
        context,
        dead_seats=[3, 5],
        eligible_last_words=[3],
    )

    assert payload == {
        "type": "DEATH_REVEALED",
        "data": {
            "dead_seats": [3, 5],
            "eligible_last_words": [3],
            "day_count": 1,
        },
        "meta": {},
    }


def test_websocket_game_engine_emits_death_revealed_payload() -> None:
    sent_payloads: list[dict[str, object]] = []
    context = GameContext(day_count=2)

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    async def run() -> None:
        engine = WebSocketGameEngine(send_json=send_json)
        await engine._notify_death_revealed(
            context,
            dead_seats=[4],
            eligible_last_words=[],
        )

    asyncio.run(run())

    assert sent_payloads == [
        {
            "type": "DEATH_REVEALED",
            "data": {
                "dead_seats": [4],
                "eligible_last_words": [],
                "day_count": 2,
            },
            "meta": {},
        }
    ]


def test_build_vote_resolved_message_carries_tally() -> None:
    payload = build_vote_resolved_message(
        votes={2: 3, 5: 1},
        ballots={1: 2, 3: 2, 6: 5, 8: 2},
        abstentions=[4],
        banished_seat=2,
        summary="2号玩家被放逐出局。",
    )

    assert payload == {
        "type": "VOTE_RESOLVED",
        "data": {
            "votes": {2: 3, 5: 1},
            "ballots": {1: 2, 3: 2, 6: 5, 8: 2},
            "abstentions": [4],
            "banished_seat": 2,
            "summary": "2号玩家被放逐出局。",
        },
        "meta": {},
    }


def test_websocket_game_engine_emits_vote_resolved_payload() -> None:
    sent_payloads: list[dict[str, object]] = []

    async def send_json(payload: dict[str, object]) -> None:
        sent_payloads.append(payload)

    async def run() -> None:
        engine = WebSocketGameEngine(send_json=send_json)
        await engine._notify_vote_resolved(
            votes={3: 2},
            ballots={1: 3, 2: 3},
            abstentions=[],
            banished_seat=3,
            summary="3号玩家被放逐出局。",
        )

    asyncio.run(run())

    assert sent_payloads == [
        {
            "type": "VOTE_RESOLVED",
            "data": {
                "votes": {3: 2},
                "ballots": {1: 3, 2: 3},
                "abstentions": [],
                "banished_seat": 3,
                "summary": "3号玩家被放逐出局。",
            },
            "meta": {},
        }
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
    assert "狼坑" in speech


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
        attach_context_bridge(context, send_json, viewer_seat_id=1)
        engine = WebSocketGameEngine(send_json=send_json)
        await engine.run_loop(context=context, max_rounds=1)

    asyncio.run(run())

    public_messages = [
        payload["data"]["message"]
        for payload in sent_payloads
        if payload["type"] == "CHAT_UPDATE" and payload["data"]["visibility"] == "public"
    ]

    assert any("狼坑" in message for message in public_messages)


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
            context.players[1].resolve_input(
                {"action_type": "SPEAK", "text": "\u6211\u662f\u9884\u8a00\u5bb6\u3002", "request_id": "input-1"}
            )
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
                "request_id": "input-1",
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


def test_resolve_human_submit_action_rejects_mismatched_request_id() -> None:
    setup_result = setup_game(rng=random.Random(7))
    player = setup_result.context.players[setup_result.human_seat_id]
    assert isinstance(player, HumanPlayer)

    async def run() -> None:
        pending = player.begin_input(request_id="input-1")

        assert resolve_human_submit_action(
            setup_result,
            {"action_type": "SPEAK", "text": "\u8fc7\u3002", "request_id": "input-0"},
        ) is False
        assert pending.done() is False

        assert resolve_human_submit_action(
            setup_result,
            {"action_type": "SPEAK", "text": "\u8fc7\u3002", "request_id": "input-1"},
        ) is True
        assert await pending == {"action_type": "SPEAK", "text": "\u8fc7\u3002", "request_id": "input-1"}

    asyncio.run(run())


def test_resolve_human_submit_action_rejects_unexpected_pending_action() -> None:
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.SEER))
    setup_result = GameSetupResult(
        context=context,
        human_seat_id=1,
        human_role=Role.SEER.value,
        human_view={},
    )
    player = context.players[1]
    assert isinstance(player, HumanPlayer)

    async def run() -> None:
        pending = player.begin_input(
            allowed_action_types={"VOTE", "PASS"},
            allowed_targets={2, 3},
        )

        assert resolve_human_submit_action(
            setup_result,
            {"action_type": "WOLF_KILL", "target": 2},
        ) is False
        assert pending.done() is False

        assert resolve_human_submit_action(
            setup_result,
            {"action_type": "VOTE", "target": 2},
        ) is True
        assert await pending == {"action_type": "VOTE", "target": 2}

    asyncio.run(run())


def test_resolve_human_submit_action_rejects_target_outside_pending_targets() -> None:
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.SEER))
    setup_result = GameSetupResult(
        context=context,
        human_seat_id=1,
        human_role=Role.SEER.value,
        human_view={},
    )
    player = context.players[1]
    assert isinstance(player, HumanPlayer)

    async def run() -> None:
        pending = player.begin_input(
            allowed_action_types={"VOTE", "PASS"},
            allowed_targets={2, 3},
            request_id="input-1",
        )

        assert resolve_human_submit_action(
            setup_result,
            {"action_type": "VOTE", "target": 9, "request_id": "input-1"},
        ) is False
        assert pending.done() is False

        assert resolve_human_submit_action(
            setup_result,
            {"action_type": "VOTE", "target": 3, "request_id": "input-1"},
        ) is True
        assert await pending == {"action_type": "VOTE", "target": 3, "request_id": "input-1"}

    asyncio.run(run())


def test_allowed_submit_action_types_match_input_requests() -> None:
    assert allowed_submit_action_types("VOTE") == {"VOTE", "PASS"}
    assert allowed_submit_action_types(
        "WITCH_ACTION",
        available_actions=["WITCH_POISON", "PASS"],
    ) == {"WITCH_POISON", "PASS"}
    assert allowed_submit_action_types(
        "WITCH_ACTION",
        available_actions=[],
    ) == set()
    assert allowed_submit_action_types("SEER_CHECK") == {"SEER_CHECK"}


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
            context.players[1].resolve_input({"action_type": "VOTE", "target": 3, "request_id": "input-1"})
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
                "request_id": "input-1",
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
            context.players[1].resolve_input({"action_type": "PASS", "request_id": "input-1"})
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
                "request_id": "input-1",
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
            context.players[1].resolve_input({"action_type": "WOLF_KILL", "target": 1, "request_id": "input-1"})
            result = await target_task
            assert result == 1
        finally:
            engine._active_context = None

    asyncio.run(run_with_context())

    assert context.get_private_log(1)[-1] == "你选择今晚击杀 1 号。"
    assert sent_payloads == [
        {
            "type": "REQUIRE_INPUT",
            "data": {
                "action_type": "WOLF_KILL",
                "request_id": "input-1",
                "prompt": "\u8bf7\u9009\u62e9\u4eca\u591c\u8981\u51fb\u6740\u7684\u5b58\u6d3b\u73a9\u5bb6\u3002",
                "allowed_targets": [1, 2, 3],
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
            context.players[1].resolve_input({"action_type": "SEER_CHECK", "target": 2, "request_id": "input-1"})
            result = await target_task
            assert result == 2
        finally:
            engine._active_context = None

    asyncio.run(run_with_context())

    assert context.get_private_log(1)[-1] == "你选择查验 2 号。"
    assert sent_payloads == [
        {
            "type": "REQUIRE_INPUT",
            "data": {
                "action_type": "SEER_CHECK",
                "request_id": "input-1",
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
            context.players[1].resolve_input({"action_type": "WITCH_POISON", "target": 2, "request_id": "input-1"})
            result = await action_task
            assert result == (None, 2)
        finally:
            engine._active_context = None

    asyncio.run(run_with_context())

    assert context.get_private_log(1)[-1] == "你对 2 号使用毒药。"
    assert sent_payloads == [
        {
            "type": "REQUIRE_INPUT",
            "data": {
                "action_type": "WITCH_ACTION",
                "request_id": "input-1",
                "prompt": "\u6628\u591c 3 \u53f7\u88ab\u51fb\u6740\uff0c\u4f60\u53ef\u4ee5\u9009\u62e9\u6551\u4eba\u3002 \u4f60\u4e5f\u53ef\u4ee5\u9009\u62e9\u6bd2\u4eba\u6216\u8df3\u8fc7\u3002",
                "allowed_targets": [2, 4],
                "available_actions": ["WITCH_SAVE", "WITCH_POISON", "PASS"],
                "save_targets": [3],
            },
            "meta": {},
        },
    ]


def test_websocket_game_engine_ignores_unavailable_human_witch_save() -> None:
    sent_payloads: list[dict[str, object]] = []
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.WITCH))
    context.add_player(HumanPlayer(seat_id=2, role=Role.WOLF))
    context.add_player(HumanPlayer(seat_id=3, role=Role.VILLAGER))

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
                    save_candidates=[],
                    poison_candidates=[2, 3],
                )
            )
            await asyncio.sleep(0)
            assert context.players[1].resolve_input({"action_type": "WITCH_SAVE", "request_id": "input-1"}) is False
            context.players[1].resolve_input({"action_type": "PASS", "request_id": "input-1"})
            result = await action_task
            assert result == (None, None)
        finally:
            engine._active_context = None

    asyncio.run(run_with_context())

    assert sent_payloads == [
        {
            "type": "REQUIRE_INPUT",
            "data": {
                "action_type": "WITCH_ACTION",
                "request_id": "input-1",
                "prompt": "\u4f60\u4e5f\u53ef\u4ee5\u9009\u62e9\u6bd2\u4eba\u6216\u8df3\u8fc7\u3002",
                "allowed_targets": [2, 3],
                "available_actions": ["WITCH_POISON", "PASS"],
                "save_targets": [],
            },
            "meta": {},
        },
    ]
    assert context.get_private_log(1)[-1] == "你选择今晚不用药。"


def test_websocket_game_engine_hides_witch_poison_when_no_targets() -> None:
    sent_payloads: list[dict[str, object]] = []
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.WITCH))

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
                    save_candidates=[],
                    poison_candidates=[],
                )
            )
            await asyncio.sleep(0)
            context.players[1].resolve_input({"action_type": "PASS", "request_id": "input-1"})
            result = await action_task
            assert result == (None, None)
        finally:
            engine._active_context = None

    asyncio.run(run_with_context())

    assert sent_payloads == [
        {
            "type": "REQUIRE_INPUT",
            "data": {
                "action_type": "WITCH_ACTION",
                "request_id": "input-1",
                "prompt": "\u8bf7\u9009\u62e9\u672c\u56de\u5408\u662f\u5426\u7528\u836f\u3002",
                "allowed_targets": [],
                "available_actions": ["PASS"],
                "save_targets": [],
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
            context.players[1].resolve_input({"action_type": "HUNTER_SHOOT", "target": 2, "request_id": "input-1"})
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
                "request_id": "input-1",
                "prompt": "\u4f60\u53ef\u4ee5\u9009\u62e9\u4e00\u540d\u5b58\u6d3b\u73a9\u5bb6\u5f00\u67aa\u3002",
                "allowed_targets": [2, 3],
            },
            "meta": {},
        },
    ]
