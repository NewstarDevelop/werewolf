import pytest

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import Player
from app.engine.night.seer_action import resolve_seer_action


def build_context() -> GameContext:
    context = GameContext()
    context.add_player(Player(seat_id=1, role=Role.SEER))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))
    return context


def test_seer_action_records_wolf_result_in_private_log() -> None:
    context = build_context()

    result = resolve_seer_action(context, seer_seat=1, target_seat=2)

    assert result == "狼人"
    assert context.get_private_log(1) == ["查验结果：2 号是狼人。"]


def test_seer_action_records_good_result_for_non_wolf() -> None:
    context = build_context()

    result = resolve_seer_action(context, seer_seat=1, target_seat=3)

    assert result == "好人"
    assert context.get_private_log(1) == ["查验结果：3 号是好人。"]


def test_seer_action_rejects_self_or_dead_target() -> None:
    context = build_context()
    context.players[3].mark_dead()

    with pytest.raises(ValueError):
        resolve_seer_action(context, seer_seat=1, target_seat=1)

    with pytest.raises(ValueError):
        resolve_seer_action(context, seer_seat=1, target_seat=3)
