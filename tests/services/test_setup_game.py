import random

from app.services.setup_game import setup_game


def test_setup_game_returns_human_identity_payload() -> None:
    result = setup_game(rng=random.Random(9))

    assert result.human_role == result.human_view["players"][result.human_seat_id - 1]["known_role"]
    assert result.human_view["private_log"] == [
        f"你的座位号是 {result.human_seat_id} 号，身份是 {result.human_role}。"
    ]


def test_setup_game_keeps_other_roles_masked_for_human_view() -> None:
    result = setup_game(rng=random.Random(15))

    other_players = [
        player for player in result.human_view["players"] if not player["is_self"]
    ]

    assert all(player["known_role"] is None for player in other_players)
