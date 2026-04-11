from app.protocols.s2c import (
    AIThinkingEnvelope,
    AIThinkingPayload,
    ChatUpdateEnvelope,
    ChatUpdatePayload,
    GameOverEnvelope,
    GameOverPayload,
    RequireInputEnvelope,
    RequireInputPayload,
    SystemMessageEnvelope,
    SystemMessagePayload,
)


def test_system_message_envelope_shape() -> None:
    payload = SystemMessageEnvelope(
        type="SYSTEM_MSG",
        data=SystemMessagePayload(message="天黑请闭眼"),
    ).model_dump()

    assert payload == {
        "type": "SYSTEM_MSG",
        "data": {"message": "天黑请闭眼"},
        "meta": {},
    }


def test_chat_update_envelope_supports_visibility() -> None:
    payload = ChatUpdateEnvelope(
        type="CHAT_UPDATE",
        data=ChatUpdatePayload(
            message="2号发言：我先听后置位。",
            seat_id=2,
            speaker="2号",
            visibility="public",
        ),
    ).model_dump()

    assert payload["data"]["seat_id"] == 2
    assert payload["data"]["visibility"] == "public"


def test_ai_thinking_envelope_marks_player_state() -> None:
    payload = AIThinkingEnvelope(
        type="AI_THINKING",
        data=AIThinkingPayload(seat_id=3, is_thinking=True, message="思考中"),
    ).model_dump()

    assert payload["data"] == {
        "seat_id": 3,
        "is_thinking": True,
        "message": "思考中",
    }


def test_require_input_envelope_carries_targets() -> None:
    payload = RequireInputEnvelope(
        type="REQUIRE_INPUT",
        data=RequireInputPayload(
            action_type="VOTE",
            prompt="请选择投票目标",
            allowed_targets=[2, 4, 6],
        ),
    ).model_dump()

    assert payload["data"]["allowed_targets"] == [2, 4, 6]


def test_game_over_envelope_reveals_roles() -> None:
    payload = GameOverEnvelope(
        type="GAME_OVER",
        data=GameOverPayload(
            winning_side="GOOD",
            summary="狼人已全部出局",
            revealed_roles={1: "SEER", 2: "WOLF"},
        ),
    ).model_dump()

    assert payload["data"]["winning_side"] == "GOOD"
    assert payload["data"]["revealed_roles"] == {1: "SEER", 2: "WOLF"}
