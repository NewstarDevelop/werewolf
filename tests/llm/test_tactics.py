from app.domain.enums import Role
from app.domain.game_context import GameContext, NightActionSnapshot
from app.domain.player import AIPlayer, Player
from app.engine.states.phase import GamePhase
from app.llm.tactics import select_ai_tactic


def test_select_wolf_tactic_uses_personality_for_fake_claim() -> None:
    context = GameContext(phase=GamePhase.DAY_SPEAKING.value, day_count=1)
    context.add_player(AIPlayer(seat_id=1, role=Role.WOLF, personality="激进悍跳"))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.SEER))

    tactic = select_ai_tactic(context, 1)

    assert tactic.label == "悍跳"
    assert "抢夺神职视角" in tactic.objective


def test_select_wolf_tactic_backstabs_pressured_teammate() -> None:
    context = GameContext(phase=GamePhase.DAY_SPEAKING.value, day_count=2)
    actor = AIPlayer(seat_id=1, role=Role.WOLF, personality="圆滑周旋")
    actor.adjust_suspicion(2, 3)
    context.add_player(actor)
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))

    tactic = select_ai_tactic(context, 1)

    assert tactic.label == "倒钩"
    assert tactic.target_seats == [2]


def test_select_good_tactic_reports_checked_wolf() -> None:
    context = GameContext(phase=GamePhase.DAY_SPEAKING.value, day_count=2)
    context.add_player(AIPlayer(seat_id=1, role=Role.SEER, personality="稳健分析"))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.night_actions.append(
        NightActionSnapshot(
            day_count=1,
            seer_seat=1,
            seer_target=2,
            seer_result="WOLF",
        )
    )

    tactic = select_ai_tactic(context, 1)

    assert tactic.label == "报验人"
    assert tactic.target_seats == [2]


def test_select_good_tactic_pushes_vote_for_high_suspicion() -> None:
    context = GameContext(phase=GamePhase.DAY_SPEAKING.value, day_count=2)
    actor = AIPlayer(seat_id=1, role=Role.VILLAGER, personality="稳健分析")
    actor.adjust_suspicion(3, 3)
    context.add_player(actor)
    context.add_player(Player(seat_id=2, role=Role.SEER))
    context.add_player(Player(seat_id=3, role=Role.WOLF))

    tactic = select_ai_tactic(context, 1)

    assert tactic.label == "归票"
    assert tactic.target_seats == [3]


def test_select_special_role_keeps_identity_when_no_pressure() -> None:
    context = GameContext(phase=GamePhase.DAY_SPEAKING.value, day_count=1)
    context.add_player(AIPlayer(seat_id=1, role=Role.WITCH, personality="沉默观察"))
    context.add_player(Player(seat_id=2, role=Role.WOLF))

    tactic = select_ai_tactic(context, 1)

    assert tactic.label == "保留身份"
    assert "不要无理由交出全部身份信息" in tactic.guidance
