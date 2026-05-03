from app.engine.states.phase import GamePhase


def test_phase_enum_covers_core_night_and_day_nodes() -> None:
    assert GamePhase.WOLF_ACTION.value == "WOLF_ACTION"
    assert GamePhase.SEER_ACTION.value == "SEER_ACTION"
    assert GamePhase.WITCH_ACTION.value == "WITCH_ACTION"
    assert GamePhase.NIGHT_END.value == "NIGHT_END"
    assert GamePhase.DEAD_LAST_WORDS.value == "DEAD_LAST_WORDS"
    assert GamePhase.DAY_SPEAKING.value == "DAY_SPEAKING"
    assert GamePhase.VOTE_RESULT.value == "VOTE_RESULT"
    assert GamePhase.BANISH_LAST_WORDS.value == "BANISH_LAST_WORDS"
