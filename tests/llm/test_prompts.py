from app.llm.prompts import (
    GOOD_SIDE_OBJECTIVE,
    NIGHT_TASK_TEMPLATE,
    SPEECH_TASK_TEMPLATE,
    SYSTEM_GUARDRAILS,
    VOTE_TASK_TEMPLATE,
    WOLF_SIDE_OBJECTIVE,
)


def test_system_guardrails_include_fourth_wall_and_length_limits() -> None:
    assert "绝不能提到 AI" in SYSTEM_GUARDRAILS
    assert "50 到 150 字" in SYSTEM_GUARDRAILS


def test_objectives_cover_both_camps() -> None:
    assert "识别狼人" in GOOD_SIDE_OBJECTIVE
    assert "隐藏同伴身份" in WOLF_SIDE_OBJECTIVE


def test_task_templates_keep_current_stage_focus() -> None:
    assert "{seat_label}" in SPEECH_TASK_TEMPLATE
    assert "投票阶段" in VOTE_TASK_TEMPLATE
    assert "夜晚行动阶段" in NIGHT_TASK_TEMPLATE
