import pytest

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import Player
from app.engine.day.voting import resolve_voting


def build_context() -> GameContext:
    context = GameContext()
    context.add_player(Player(seat_id=1, role=Role.SEER))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))
    context.add_player(Player(seat_id=4, role=Role.VILLAGER))
    return context


def test_voting_banishes_unique_highest_target() -> None:
    context = build_context()

    result = resolve_voting(
        context,
        votes_by_voter={1: 2, 2: 3, 3: 2, 4: None},
    )

    assert result.votes == {2: 2, 3: 1}
    assert result.abstentions == [4]
    assert result.banished_seat == 2
    assert result.summary == "2号玩家被放逐出局。"
    assert context.players[2].is_alive is False


def test_voting_keeps_everyone_alive_on_tie() -> None:
    context = build_context()

    result = resolve_voting(
        context,
        votes_by_voter={1: 2, 2: 3, 3: 2, 4: 3},
    )

    assert result.banished_seat is None
    assert result.summary == "出现平票，本轮无人出局。"
    assert all(player.is_alive for player in context.players.values())


def test_voting_requires_all_alive_players_and_alive_targets() -> None:
    context = build_context()

    with pytest.raises(ValueError):
        resolve_voting(context, votes_by_voter={1: 2, 2: 3, 3: 2})

    with pytest.raises(ValueError):
        resolve_voting(context, votes_by_voter={1: 2, 2: 5, 3: 2, 4: None})
