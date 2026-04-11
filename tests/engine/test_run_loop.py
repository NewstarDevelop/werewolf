import asyncio
import random

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import Player
from app.engine.game_engine import GameEngine
from app.engine.states.phase import GamePhase


def test_run_loop_reaches_core_phases() -> None:
    engine = GameEngine(rng=random.Random(5))

    context = asyncio.run(engine.run_loop(max_rounds=1))

    assert context.phase == GamePhase.GAME_OVER.value
    assert context.public_chat_history[0] == "游戏开始，分配身份完毕。"
    assert "天黑请闭眼。" in context.public_chat_history
    assert any(message.startswith("天亮了。") for message in context.public_chat_history)
    assert "进入投票阶段。" in context.public_chat_history


def test_run_loop_stops_immediately_when_win_condition_is_met() -> None:
    context = GameContext()
    context.add_player(Player(seat_id=1, role=Role.VILLAGER))
    context.add_player(Player(seat_id=2, role=Role.SEER))

    engine = GameEngine()
    final_context = asyncio.run(engine.run_loop(context=context))

    assert final_context.phase == GamePhase.GAME_OVER.value
    assert final_context.public_chat_history[-1] == "狼人已全部出局，好人阵营获胜。"


def test_run_loop_executes_night_handlers_and_private_logs() -> None:
    engine = GameEngine(rng=random.Random(2))

    context = asyncio.run(engine.run_loop(max_rounds=1))

    seer_seat = next(
        seat_id
        for seat_id, player in context.players.items()
        if player.role is Role.SEER
    )
    wolf_seat = next(
        seat_id
        for seat_id, player in context.players.items()
        if player.role is Role.WOLF and "Alpha 狼决定击杀" in " ".join(context.get_private_log(seat_id))
    )

    assert context.get_private_log(seer_seat)
    assert "查验结果：" in context.get_private_log(seer_seat)[0]
    assert "Alpha 狼决定击杀" in context.get_private_log(wolf_seat)[0]
