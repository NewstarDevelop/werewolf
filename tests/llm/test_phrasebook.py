from app.llm.phrasebook import (
    TABLE_TALK_TERMS,
    phrasebook_prompt_guide,
    render_checked_wolf_speech,
    render_default_speech,
    render_tactic_speech,
)


def test_phrasebook_prompt_guide_contains_table_terms_and_tactics() -> None:
    guide = phrasebook_prompt_guide()

    assert "查杀" in guide
    assert "警徽流" in guide
    assert "狼坑" in guide
    assert "悍跳" in guide
    assert "倒钩" in guide
    assert set(["金水", "票型", "抗推"]).issubset(TABLE_TALK_TERMS)


def test_render_checked_wolf_speech_uses_werewolf_terms() -> None:
    speech = render_checked_wolf_speech(3)

    assert "3号查杀" in speech
    assert "警徽流" in speech
    assert "票型" in speech


def test_render_tactic_speech_returns_tactic_specific_table_talk() -> None:
    assert "跳预言家" in (render_tactic_speech("悍跳", 4) or "")
    assert "轻踩" in (render_tactic_speech("倒钩", 2) or "")
    assert "归5号" in (render_tactic_speech("归票", 5) or "")
    assert "狼坑" in (render_tactic_speech("盘狼坑") or "")
    assert render_tactic_speech("未知") is None


def test_render_default_speech_keeps_wait_and_table_analysis() -> None:
    speech = render_default_speech()

    assert "先听后置位" in speech
    assert "站边变化" in speech
    assert "狼坑" in speech
