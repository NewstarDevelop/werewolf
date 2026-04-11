import random
from collections import Counter

from app.domain.enums import Role
from app.domain.player import AIPlayer, HumanPlayer
from app.engine.init import initialize_game


def test_initialize_game_creates_nine_players_with_one_human() -> None:
    result = initialize_game(rng=random.Random(7))

    human_players = [
        player for player in result.context.players.values() if isinstance(player, HumanPlayer)
    ]
    ai_players = [
        player for player in result.context.players.values() if isinstance(player, AIPlayer)
    ]

    assert len(result.context.players) == 9
    assert len(human_players) == 1
    assert len(ai_players) == 8
    assert result.human_seat_id == human_players[0].seat_id
    assert result.human_role == human_players[0].role


def test_initialize_game_uses_expected_role_deck() -> None:
    result = initialize_game(rng=random.Random(12))

    role_counts = Counter(player.role for player in result.context.players.values())

    assert role_counts == {
        Role.WOLF: 3,
        Role.VILLAGER: 3,
        Role.SEER: 1,
        Role.WITCH: 1,
        Role.HUNTER: 1,
    }


def test_initialize_game_assigns_unique_ai_personalities_and_boot_log() -> None:
    result = initialize_game(rng=random.Random(21))
    ai_players = [
        player for player in result.context.players.values() if isinstance(player, AIPlayer)
    ]

    assert len({player.personality for player in ai_players}) == 8
    assert result.context.public_chat_history == ["游戏开始，分配身份完毕。"]
