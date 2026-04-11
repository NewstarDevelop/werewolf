import pytest

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer, HumanPlayer, Player
from app.engine.night.wolf_action import resolve_wolf_action


def build_context(*players: Player) -> GameContext:
    context = GameContext()
    for player in players:
        context.add_player(player)
    return context


def test_human_wolf_target_takes_priority() -> None:
    context = build_context(
        HumanPlayer(seat_id=1, role=Role.WOLF),
        AIPlayer(seat_id=2, role=Role.WOLF, personality="aggressive"),
        Player(seat_id=3, role=Role.SEER),
        Player(seat_id=4, role=Role.VILLAGER),
    )

    target = resolve_wolf_action(context, human_target=4)

    assert target == 4
    assert context.killed_tonight == [4]


def test_all_ai_wolves_use_alpha_choice() -> None:
    context = build_context(
        AIPlayer(seat_id=2, role=Role.WOLF, personality="aggressive"),
        AIPlayer(seat_id=5, role=Role.WOLF, personality="steady"),
        Player(seat_id=3, role=Role.SEER),
        Player(seat_id=4, role=Role.VILLAGER),
    )

    target = resolve_wolf_action(context)

    assert target == 3
    assert context.killed_tonight == [3]
    assert context.get_private_log(2) == ["Alpha 狼决定击杀 3 号。"]


def test_all_ai_wolves_can_use_explicit_ai_target() -> None:
    context = build_context(
        AIPlayer(seat_id=2, role=Role.WOLF, personality="aggressive"),
        AIPlayer(seat_id=5, role=Role.WOLF, personality="steady"),
        Player(seat_id=3, role=Role.SEER),
        Player(seat_id=4, role=Role.VILLAGER),
    )

    target = resolve_wolf_action(context, ai_target=4)

    assert target == 4
    assert context.killed_tonight == [4]


def test_human_wolf_cannot_choose_invalid_target() -> None:
    context = build_context(
        HumanPlayer(seat_id=1, role=Role.WOLF),
        Player(seat_id=2, role=Role.VILLAGER, is_alive=False),
        Player(seat_id=3, role=Role.SEER),
    )

    with pytest.raises(ValueError):
        resolve_wolf_action(context, human_target=2)
