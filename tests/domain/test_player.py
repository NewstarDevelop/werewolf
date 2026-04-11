import asyncio

from app.domain.enums import Role
from app.domain.player import AIPlayer, HumanPlayer, Player


def test_player_can_be_marked_dead() -> None:
    player = Player(seat_id=1, role=Role.VILLAGER)

    player.mark_dead()

    assert player.is_alive is False


def test_human_player_keeps_pending_input_slot() -> None:
    loop = asyncio.new_event_loop()
    try:
        future = loop.create_future()
        player = HumanPlayer(seat_id=2, role=Role.SEER, pending_input=future)

        assert player.is_human is True
        assert player.pending_input is future
    finally:
        loop.close()


def test_ai_player_records_private_memory() -> None:
    player = AIPlayer(seat_id=3, role=Role.WOLF, personality="aggressive")

    player.remember("6号和8号是狼同伴")

    assert player.is_human is False
    assert player.private_memory == ["6号和8号是狼同伴"]
