from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer, Player
from app.llm.builders import build_night_prompt, build_speech_prompt, build_vote_prompt


def build_context() -> GameContext:
    context = GameContext(phase="DAY_SPEAKING", day_count=2)
    context.add_player(AIPlayer(seat_id=2, role=Role.WOLF, personality="激进悍跳"))
    context.add_player(Player(seat_id=3, role=Role.SEER))
    context.add_player(Player(seat_id=4, role=Role.VILLAGER))
    context.add_public_message("4号质疑2号视角。")
    context.add_private_message(2, "你的狼同伴是 6号 和 8号。")
    return context


def test_build_speech_prompt_includes_role_goal_and_private_view() -> None:
    prompt = build_speech_prompt(build_context(), seat_id=2)

    assert "隐藏同伴身份" in prompt.system_prompt
    assert "激进悍跳" in prompt.context_prompt
    assert "你的狼同伴是 6号 和 8号。" in prompt.context_prompt
    assert "现在轮到 2号 发言" in prompt.task_prompt


def test_build_vote_prompt_reuses_same_context_sections() -> None:
    prompt = build_vote_prompt(build_context(), seat_id=2, allowed_targets=[3, 4])

    assert "投票阶段" in prompt.task_prompt
    assert "公开历史" in prompt.context_prompt
    assert "[3, 4]" in prompt.task_prompt


def test_build_night_prompt_keeps_night_task_wording() -> None:
    prompt = build_night_prompt(build_context(), seat_id=2, allowed_targets=[3, 4])

    assert "夜晚行动阶段" in prompt.task_prompt
    assert "[3, 4]" in prompt.task_prompt
