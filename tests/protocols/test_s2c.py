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
    SettlementDayPayload,
    SettlementEventPayload,
    SettlementNightPayload,
    SettlementPlayerPayload,
    SettlementRecapPayload,
    SettlementSpeechPayload,
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
            ballots={1: 2, 3: 2, 6: 5, 8: 2},
            abstentions=[4],
            banished_seat=2,
            summary="2号玩家被放逐出局。",
        ),
    ).model_dump()

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


def test_require_input_envelope_carries_targets() -> None:
    payload = RequireInputEnvelope(
        type="REQUIRE_INPUT",
        data=RequireInputPayload(
            action_type="VOTE",
            request_id="input-1",
            prompt="请选择投票目标",
            allowed_targets=[2, 4, 6],
        ),
    ).model_dump()

    assert payload["data"]["request_id"] == "input-1"
    assert payload["data"]["allowed_targets"] == [2, 4, 6]


def test_require_input_envelope_can_carry_witch_action_options() -> None:
    payload = RequireInputEnvelope(
        type="REQUIRE_INPUT",
        data=RequireInputPayload(
            action_type="WITCH_ACTION",
            request_id="input-2",
            prompt="请选择女巫行动",
            allowed_targets=[2, 4],
            available_actions=["WITCH_SAVE", "WITCH_POISON", "PASS"],
            save_targets=[3],
        ),
    ).model_dump()

    assert payload["data"]["available_actions"] == ["WITCH_SAVE", "WITCH_POISON", "PASS"]
    assert payload["data"]["save_targets"] == [3]


def test_require_input_envelope_supports_hunter_shoot() -> None:
    payload = RequireInputEnvelope(
        type="REQUIRE_INPUT",
        data=RequireInputPayload(
            action_type="HUNTER_SHOOT",
            request_id="input-3",
            prompt="请选择开枪目标",
            allowed_targets=[2, 5],
        ),
    ).model_dump()

    assert payload["data"]["action_type"] == "HUNTER_SHOOT"


def test_settlement_recap_payload_carries_revealed_review() -> None:
    payload = SettlementRecapPayload(
        day_count=2,
        outcome_reason="狼人全灭。",
        role_reveal_summary="狼人：2号；神职：1号；平民：无。",
        players=[
            SettlementPlayerPayload(
                seat_id=1,
                role_code="SEER",
                side="GOOD",
                is_alive=True,
                is_human=True,
            )
        ],
        key_events=[
            SettlementEventPayload(
                day_count=1,
                phase="DAY_START",
                event_type="NIGHT_DEATH",
                message="天亮了。昨夜死亡的是 3号。",
                target_seats=[3],
            )
        ],
        timeline=[
            SettlementEventPayload(
                day_count=1,
                phase="DAY_START",
                event_type="NIGHT_DEATH",
                message="天亮了。昨夜死亡的是 3号。",
                target_seats=[3],
            ),
            SettlementEventPayload(
                day_count=1,
                phase="DAY_SPEAKING",
                event_type="SPEECH",
                message="1号发言：我查杀2号。",
                actor_seat=1,
            ),
        ],
        nights=[
            SettlementNightPayload(
                day_count=1,
                wolf_target=3,
                seer_seat=1,
                seer_target=2,
                seer_result="WOLF",
                witch_save_target=3,
                dead_seats=[],
            )
        ],
        days=[
            SettlementDayPayload(
                day_count=1,
                speeches=[
                    SettlementSpeechPayload(
                        seat_id=1,
                        message="1号发言：我查杀2号。",
                        event_type="SPEECH",
                    )
                ],
                vote_explanation="2号以 3 票成为最高票，被放逐出局。",
            )
        ],
        final_vote=VoteResolvedPayload(
            votes={2: 3},
            ballots={1: 2, 3: 2, 4: 2},
            abstentions=[],
            banished_seat=2,
            summary="2号玩家被放逐出局。",
        ),
    ).model_dump()

    assert payload["day_count"] == 2
    assert payload["players"][0]["role_code"] == "SEER"
    assert payload["key_events"][0]["event_type"] == "NIGHT_DEATH"
    assert payload["nights"][0]["wolf_target"] == 3
    assert payload["days"][0]["speeches"][0]["seat_id"] == 1
    assert payload["outcome_reason"] == "狼人全灭。"
    assert payload["role_reveal_summary"] == "狼人：2号；神职：1号；平民：无。"
    assert payload["timeline"][1]["event_type"] == "SPEECH"
    assert payload["final_vote"]["banished_seat"] == 2


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
    assert payload["data"]["recap"] is None


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
    assert payload["data"]["recap"] is None
