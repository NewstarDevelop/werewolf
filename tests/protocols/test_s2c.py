from app.protocols.s2c import (
    AIThinkingEnvelope,
    AIThinkingPayload,
    ChatUpdateEnvelope,
    ChatUpdatePayload,
    DeathRevealedEnvelope,
    DeathRevealedPayload,
    GameOverEnvelope,
    GameOverPayload,
    PhaseChangedEnvelope,
    PhaseChangedPayload,
    PlayerStatePatch,
    PlayerStatePatchEnvelope,
    PlayerStatePatchPayload,
    RequireInputEnvelope,
    RequireInputPayload,
    SystemMessageEnvelope,
    SystemMessagePayload,
    VoteResolvedEnvelope,
    VoteResolvedPayload,
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


def test_player_state_patch_envelope_carries_structured_updates() -> None:
    payload = PlayerStatePatchEnvelope(
        type="PLAYER_STATE_PATCH",
        data=PlayerStatePatchPayload(
            players=[
                PlayerStatePatch(
                    seat_id=4,
                    is_alive=False,
                    is_human=True,
                    role_code="WITCH",
                    is_thinking=False,
                )
            ],
        ),
    ).model_dump()

    assert payload == {
        "type": "PLAYER_STATE_PATCH",
        "data": {
            "players": [
                {
                    "seat_id": 4,
                    "is_alive": False,
                    "is_human": True,
                    "role_code": "WITCH",
                    "is_thinking": False,
                }
            ],
        },
        "meta": {},
    }


def test_phase_changed_envelope_carries_phase_and_day() -> None:
    payload = PhaseChangedEnvelope(
        type="PHASE_CHANGED",
        data=PhaseChangedPayload(phase="NIGHT_START", day_count=2),
    ).model_dump()

    assert payload == {
        "type": "PHASE_CHANGED",
        "data": {
            "phase": "NIGHT_START",
            "day_count": 2,
        },
        "meta": {},
    }


def test_death_revealed_envelope_carries_dead_seats_and_last_words() -> None:
    payload = DeathRevealedEnvelope(
        type="DEATH_REVEALED",
        data=DeathRevealedPayload(
            dead_seats=[3, 5],
            eligible_last_words=[3, 5],
            day_count=1,
        ),
    ).model_dump()

    assert payload == {
        "type": "DEATH_REVEALED",
        "data": {
            "dead_seats": [3, 5],
            "eligible_last_words": [3, 5],
            "day_count": 1,
        },
        "meta": {},
    }


def test_vote_resolved_envelope_carries_tally_and_banishment() -> None:
    payload = VoteResolvedEnvelope(
        type="VOTE_RESOLVED",
        data=VoteResolvedPayload(
            votes={2: 3, 5: 1},
            abstentions=[4],
            banished_seat=2,
            summary="2号玩家被放逐出局。",
        ),
    ).model_dump()

    assert payload == {
        "type": "VOTE_RESOLVED",
        "data": {
            "votes": {2: 3, 5: 1},
            "abstentions": [4],
            "banished_seat": 2,
            "summary": "2号玩家被放逐出局。",
        },
        "meta": {},
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


def test_require_input_envelope_supports_hunter_shoot() -> None:
    payload = RequireInputEnvelope(
        type="REQUIRE_INPUT",
        data=RequireInputPayload(
            action_type="HUNTER_SHOOT",
            prompt="请选择开枪目标",
            allowed_targets=[2, 5],
        ),
    ).model_dump()

    assert payload["data"]["action_type"] == "HUNTER_SHOOT"


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


def test_game_over_envelope_allows_draw_safety_stop() -> None:
    payload = GameOverEnvelope(
        type="GAME_OVER",
        data=GameOverPayload(
            winning_side="DRAW",
            summary="夜尽未分胜负，本局暂止。",
            revealed_roles={1: "WOLF", 2: "VILLAGER"},
        ),
    ).model_dump()

    assert payload["data"]["winning_side"] == "DRAW"
    assert payload["data"]["summary"] == "夜尽未分胜负，本局暂止。"
