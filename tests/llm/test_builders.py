import json

from app.domain.enums import Role
from app.domain.game_context import GameContext, NightActionSnapshot, VoteSnapshot
from app.domain.player import AIPlayer, Player
from app.llm.builders import build_night_prompt, build_speech_prompt, build_vote_prompt


def build_context() -> GameContext:
    context = GameContext(phase="DAY_SPEAKING", day_count=2)
    context.add_player(AIPlayer(seat_id=2, role=Role.WOLF, personality="激进悍跳"))
    context.add_player(Player(seat_id=3, role=Role.SEER))
    context.add_player(Player(seat_id=4, role=Role.VILLAGER))
    context.add_public_message("2号发言：我先站边自己听后置位。")
    context.add_public_message("4号质疑2号视角。")
    context.add_private_message(2, "你的狼同伴是 6号 和 8号。")
    return context


def extract_view_json(context_prompt: str) -> dict[str, object]:
    for line in context_prompt.splitlines():
        if line.startswith("玩家视图JSON："):
            payload = line.removeprefix("玩家视图JSON：")
            decoded = json.loads(payload)
            assert isinstance(decoded, dict)
            return decoded
    raise AssertionError("missing 玩家视图JSON section")


def test_build_speech_prompt_includes_role_goal_and_private_view() -> None:
    prompt = build_speech_prompt(build_context(), seat_id=2)
    view = extract_view_json(prompt.context_prompt)

    assert "隐藏同伴身份" in prompt.system_prompt
    assert "不要主动暴露狼同伴" in prompt.system_prompt
    assert "局内话术偏好" in prompt.system_prompt
    assert "查杀" in prompt.system_prompt
    assert "激进悍跳" in prompt.context_prompt
    assert "局势摘要" in prompt.context_prompt
    assert "本轮战术目标" in prompt.context_prompt
    assert "立场摘要" in prompt.context_prompt
    assert "2号发言：我先站边自己听后置位。" in prompt.context_prompt
    assert "你的狼同伴是 6号 和 8号。" in prompt.context_prompt
    assert view["private_log"] == ["你的狼同伴是 6号 和 8号。"]
    assert view["players"] == [
        {"is_alive": True, "is_self": True, "known_role": "WOLF", "seat_id": 2},
        {"is_alive": True, "is_self": False, "known_role": None, "seat_id": 3},
        {"is_alive": True, "is_self": False, "known_role": None, "seat_id": 4},
    ]
    assert "现在轮到 2号 发言" in prompt.task_prompt


def test_build_speech_prompt_serializes_view_as_stable_json() -> None:
    prompt = build_speech_prompt(build_context(), seat_id=2)

    assert '"players":[{"is_alive":true' in prompt.context_prompt
    assert "'known_role'" not in prompt.context_prompt
    assert "玩家视图：" not in prompt.context_prompt


def test_build_speech_prompt_includes_wolf_team_strategy_hint() -> None:
    context = build_context()
    context.add_player(Player(seat_id=5, role=Role.WOLF))

    prompt = build_speech_prompt(context, seat_id=2)

    assert "战术连续性提示" in prompt.context_prompt
    assert "狼队友存活：5号" in prompt.context_prompt
    assert "倒钩" in prompt.context_prompt


def test_build_speech_prompt_includes_explicit_wolf_tactic() -> None:
    context = build_context()
    context.add_player(Player(seat_id=5, role=Role.WOLF))

    prompt = build_speech_prompt(context, seat_id=2)

    assert "本轮战术目标：悍跳" in prompt.context_prompt
    assert "公开打法" in prompt.context_prompt


def test_build_vote_prompt_includes_previous_vote_continuity() -> None:
    context = build_context()
    context.last_vote_result = VoteSnapshot(
        day_count=1,
        votes={3: 1},
        ballots={2: 3},
        abstentions=[],
        banished_seat=3,
        summary="3号玩家被放逐出局。",
    )

    prompt = build_vote_prompt(context, seat_id=2, allowed_targets=[3, 4])

    assert "你上一轮投票给 3号" in prompt.context_prompt
    assert "3号玩家被放逐出局。" in prompt.context_prompt


def test_build_speech_prompt_includes_seer_check_chain_and_badge_flow() -> None:
    context = GameContext(phase="DAY_SPEAKING", day_count=2)
    context.add_player(AIPlayer(seat_id=1, role=Role.SEER, personality="稳健报验"))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))
    context.night_actions.append(
        NightActionSnapshot(
            day_count=1,
            seer_seat=1,
            seer_target=2,
            seer_result="WOLF",
        )
    )

    prompt = build_speech_prompt(context, seat_id=1)

    assert "第1夜验2号=狼人" in prompt.context_prompt
    assert "本轮战术目标：报验人；目标：2号" in prompt.context_prompt
    assert "警徽流" in prompt.context_prompt


def test_build_prompt_includes_ai_stance_summary() -> None:
    context = build_context()
    player = context.players[2]
    assert isinstance(player, AIPlayer)
    player.adjust_suspicion(4, 3)
    player.adjust_trust(3, 2)

    prompt = build_speech_prompt(context, seat_id=2)

    assert "立场摘要：怀疑：4号(3)；信任：3号(2)" in prompt.context_prompt


def test_build_vote_prompt_reuses_same_context_sections() -> None:
    prompt = build_vote_prompt(build_context(), seat_id=2, allowed_targets=[3, 4])

    assert "投票阶段" in prompt.task_prompt
    assert "公开历史" in prompt.context_prompt
    assert "[3, 4]" in prompt.task_prompt


def test_build_night_prompt_keeps_night_task_wording() -> None:
    prompt = build_night_prompt(build_context(), seat_id=2, allowed_targets=[3, 4])

    assert "夜晚行动阶段" in prompt.task_prompt
    assert "[3, 4]" in prompt.task_prompt
