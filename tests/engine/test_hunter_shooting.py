import pytest

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import Player
from app.engine.night.hunter_shooting import resolve_hunter_shooting


def build_context() -> GameContext:
    context = GameContext()
    context.add_player(Player(seat_id=1, role=Role.HUNTER, is_alive=False))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))
    return context


def test_dead_hunter_can_shoot_living_target() -> None:
    context = build_context()

    result = resolve_hunter_shooting(context, hunter_seat=1, target_seat=2)

    assert result.can_shoot is True
    assert result.shot_seat == 2
    assert result.summary == "1号猎人开枪带走了2号玩家。"
    assert context.players[2].is_alive is False


def test_poisoned_hunter_loses_shooting_right() -> None:
    context = build_context()

    result = resolve_hunter_shooting(context, hunter_seat=1, poisoned=True)

    assert result.can_shoot is False
    assert result.shot_seat is None
    assert result.summary == "1号猎人被毒死，无法开枪。"
    assert context.players[2].is_alive is True


def test_hunter_shooting_rejects_self_or_dead_target() -> None:
    context = build_context()
    context.players[2].mark_dead()

    with pytest.raises(ValueError):
        resolve_hunter_shooting(context, hunter_seat=1, target_seat=1)

    with pytest.raises(ValueError):
        resolve_hunter_shooting(context, hunter_seat=1, target_seat=2)


def test_hunter_shooting_requires_dead_hunter_role() -> None:
    context = GameContext()
    context.add_player(Player(seat_id=1, role=Role.HUNTER))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER, is_alive=False))

    with pytest.raises(ValueError):
        resolve_hunter_shooting(context, hunter_seat=1, target_seat=2)

    with pytest.raises(ValueError):
        resolve_hunter_shooting(context, hunter_seat=3, target_seat=2)
