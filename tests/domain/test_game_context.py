from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer, HumanPlayer, Player
from app.domain.view_mask import build_player_view


def build_context() -> GameContext:
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.SEER))
    context.add_player(AIPlayer(seat_id=2, role=Role.WOLF, personality="sharp"))
    context.add_player(AIPlayer(seat_id=3, role=Role.WOLF, personality="steady"))
    context.add_player(Player(seat_id=4, role=Role.VILLAGER))
    return context


def test_game_context_tracks_messages_and_alive_players() -> None:
    context = build_context()
    context.add_public_message("天黑请闭眼")
    context.add_private_message(2, "你和3号是狼同伴")
    context.players[4].mark_dead()
    context.mark_killed_tonight(4, cause="wolf")

    assert context.public_chat_history == ["天黑请闭眼"]
    assert context.get_private_log(2) == ["你和3号是狼同伴"]
    assert context.players[2].private_memory == ["你和3号是狼同伴"]
    assert context.alive_seat_ids() == [1, 2, 3]
    assert context.killed_tonight == [4]
    assert context.death_causes_for(4) == {"wolf"}


def test_game_context_can_clear_night_deaths() -> None:
    context = build_context()
    context.mark_killed_tonight(2, cause="wolf")
    context.mark_killed_tonight(2, cause="poison")

    context.clear_night_deaths()

    assert context.killed_tonight == []
    assert context.night_death_causes == {}


def test_game_context_notifies_public_and_private_message_listeners() -> None:
    context = build_context()
    public_messages: list[str] = []
    private_messages: list[tuple[int, str]] = []

    context.on_public_message(public_messages.append)
    context.on_private_message(lambda seat_id, message: private_messages.append((seat_id, message)))

    context.add_public_message("游戏开始")
    context.add_private_message(1, "你的身份是预言家")

    assert public_messages == ["游戏开始"]
    assert private_messages == [(1, "你的身份是预言家")]


def test_view_mask_hides_unpublished_roles_from_non_wolves() -> None:
    context = build_context()

    player_view = build_player_view(context, viewer_seat=1)

    assert player_view["private_log"] == []
    assert player_view["players"] == [
        {"seat_id": 1, "is_alive": True, "is_self": True, "known_role": "SEER"},
        {"seat_id": 2, "is_alive": True, "is_self": False, "known_role": None},
        {"seat_id": 3, "is_alive": True, "is_self": False, "known_role": None},
        {"seat_id": 4, "is_alive": True, "is_self": False, "known_role": None},
    ]


def test_view_mask_reveals_wolf_teammates_only_to_wolves() -> None:
    context = build_context()

    player_view = build_player_view(context, viewer_seat=2)

    assert player_view["players"][0]["known_role"] is None
    assert player_view["players"][1]["known_role"] == "WOLF"
    assert player_view["players"][2]["known_role"] == "WOLF"
    assert player_view["players"][3]["known_role"] is None


def test_view_mask_hides_killed_tonight_from_non_witch_viewers() -> None:
    context = build_context()
    context.add_player(AIPlayer(seat_id=5, role=Role.WITCH, personality="careful"))
    context.mark_killed_tonight(4, cause="wolf")

    for non_witch_seat in (1, 2, 3, 4):
        view = build_player_view(context, viewer_seat=non_witch_seat)
        assert view["killed_tonight"] == [], (
            f"seat {non_witch_seat} must not see killed_tonight"
        )


def test_view_mask_reveals_killed_tonight_to_witch_only() -> None:
    context = build_context()
    context.add_player(AIPlayer(seat_id=5, role=Role.WITCH, personality="careful"))
    context.mark_killed_tonight(4, cause="wolf")

    view = build_player_view(context, viewer_seat=5)

    assert view["killed_tonight"] == [4]
