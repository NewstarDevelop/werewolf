from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import Player
from app.engine.check_win import check_win


def build_context(*roles: Role) -> GameContext:
    context = GameContext()
    for index, role in enumerate(roles, start=1):
        context.add_player(Player(seat_id=index, role=role))
    return context


def test_good_side_wins_when_all_wolves_die() -> None:
    context = build_context(Role.WOLF, Role.VILLAGER, Role.SEER)
    context.players[1].mark_dead()

    result = check_win(context)

    assert result == {
        "winning_side": "GOOD",
        "summary": "狼人已全部出局，好人阵营获胜。",
    }


def test_wolf_side_wins_when_all_villagers_die() -> None:
    context = build_context(Role.WOLF, Role.WOLF, Role.SEER, Role.VILLAGER)
    context.players[4].mark_dead()

    result = check_win(context)

    assert result == {
        "winning_side": "WOLF",
        "summary": "平民已全部出局，狼人阵营获胜。",
    }


def test_wolf_side_wins_when_all_special_roles_die() -> None:
    context = build_context(Role.WOLF, Role.VILLAGER, Role.SEER, Role.WITCH)
    context.players[3].mark_dead()
    context.players[4].mark_dead()

    result = check_win(context)

    assert result == {
        "winning_side": "WOLF",
        "summary": "神职已全部出局，狼人阵营获胜。",
    }


def test_game_continues_when_both_camps_still_have_paths() -> None:
    context = build_context(Role.WOLF, Role.VILLAGER, Role.SEER)

    assert check_win(context) is None
