import pytest

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import Player
from app.engine.night.witch_action import WitchResources, resolve_witch_action


def build_context() -> GameContext:
    context = GameContext()
    context.add_player(Player(seat_id=1, role=Role.WITCH))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))
    context.add_player(Player(seat_id=4, role=Role.SEER))
    return context


def test_witch_can_save_target_in_killed_tonight() -> None:
    context = build_context()
    context.mark_killed_tonight(3)
    resources = WitchResources()

    updated = resolve_witch_action(context, witch_seat=1, resources=resources, save_target=3)

    assert context.killed_tonight == []
    assert updated.has_antidote is False
    assert updated.has_poison is True


def test_witch_can_poison_alive_target() -> None:
    context = build_context()
    resources = WitchResources()

    updated = resolve_witch_action(context, witch_seat=1, resources=resources, poison_target=2)

    assert context.killed_tonight == [2]
    assert updated.has_antidote is True
    assert updated.has_poison is False


def test_witch_cannot_self_save_or_reuse_missing_items() -> None:
    context = build_context()
    context.mark_killed_tonight(1)

    with pytest.raises(ValueError):
        resolve_witch_action(
            context,
            witch_seat=1,
            resources=WitchResources(),
            save_target=1,
        )

    with pytest.raises(ValueError):
        resolve_witch_action(
            context,
            witch_seat=1,
            resources=WitchResources(has_antidote=False),
            save_target=3,
        )

    with pytest.raises(ValueError):
        resolve_witch_action(
            context,
            witch_seat=1,
            resources=WitchResources(has_poison=False),
            poison_target=2,
        )
