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


def test_human_player_can_begin_resolve_and_clear_input() -> None:
    async def run() -> None:
        player = HumanPlayer(seat_id=2, role=Role.SEER)

        pending = player.begin_input()
        resolved = player.resolve_input({"action_type": "SPEAK", "text": "过"})

        assert player.pending_input is pending
        assert resolved is True
        assert await pending == {"action_type": "SPEAK", "text": "过"}

        player.clear_input()
        assert player.pending_input is None
        assert player.pending_allowed_targets is None
        assert player.pending_request_id is None

    asyncio.run(run())


def test_human_player_rejects_mismatched_pending_request_id() -> None:
    async def run() -> None:
        player = HumanPlayer(seat_id=2, role=Role.SEER)

        pending = player.begin_input(request_id="input-1")

        assert player.resolve_input({"action_type": "SPEAK", "request_id": "input-0"}) is False
        assert pending.done() is False

        assert player.resolve_input({"action_type": "SPEAK", "request_id": "input-1"}) is True
        assert await pending == {"action_type": "SPEAK", "request_id": "input-1"}

    asyncio.run(run())


def test_human_player_cancels_stale_pending_input_when_reused() -> None:
    async def run() -> None:
        player = HumanPlayer(seat_id=2, role=Role.SEER)

        stale_pending = player.begin_input(request_id="input-1")
        fresh_pending = player.begin_input(request_id="input-2")

        assert stale_pending.cancelled() is True
        assert player.pending_input is fresh_pending

        assert player.resolve_input({"action_type": "SPEAK", "request_id": "input-2"}) is True
        assert await fresh_pending == {"action_type": "SPEAK", "request_id": "input-2"}

    asyncio.run(run())


def test_human_player_rejects_target_outside_pending_allowed_targets() -> None:
    async def run() -> None:
        player = HumanPlayer(seat_id=2, role=Role.SEER)

        pending = player.begin_input(
            allowed_action_types={"VOTE", "PASS"},
            allowed_targets={3, 4},
            request_id="input-1",
        )

        assert player.resolve_input({"action_type": "VOTE", "target": 5, "request_id": "input-1"}) is False
        assert pending.done() is False

        assert player.resolve_input({"action_type": "VOTE", "target": 4, "request_id": "input-1"}) is True
        assert await pending == {"action_type": "VOTE", "target": 4, "request_id": "input-1"}

    asyncio.run(run())


def test_human_player_rejects_unexpected_target_for_untargeted_action() -> None:
    async def run() -> None:
        player = HumanPlayer(seat_id=2, role=Role.SEER)

        pending = player.begin_input(
            allowed_action_types={"VOTE", "PASS"},
            allowed_targets={3, 4},
            request_id="input-1",
        )

        assert player.resolve_input({"action_type": "PASS", "target": 3, "request_id": "input-1"}) is False
        assert pending.done() is False

        assert player.resolve_input({"action_type": "PASS", "request_id": "input-1"}) is True
        assert await pending == {"action_type": "PASS", "request_id": "input-1"}

    asyncio.run(run())


def test_ai_player_records_private_memory() -> None:
    player = AIPlayer(seat_id=3, role=Role.WOLF, personality="aggressive")

    player.remember("6号和8号是狼同伴")

    assert player.is_human is False
    assert player.private_memory == ["6号和8号是狼同伴"]


def test_ai_player_tracks_stance_scores() -> None:
    player = AIPlayer(seat_id=3, role=Role.WOLF, personality="aggressive")

    player.adjust_suspicion(5, 2)
    player.adjust_suspicion(4, 1)
    player.adjust_suspicion(5, -1)
    player.adjust_trust(2, 3)
    player.adjust_trust(3, 10)

    assert player.top_suspicions() == [(4, 1), (5, 1)]
    assert player.top_trusts() == [(2, 3)]
