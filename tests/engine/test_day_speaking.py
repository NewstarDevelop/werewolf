import asyncio

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer, HumanPlayer, Player
from app.engine.day.day_speaking import build_speaking_order, run_day_speaking


def build_context() -> GameContext:
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.SEER))
    context.add_player(AIPlayer(seat_id=2, role=Role.WOLF, personality="aggressive"))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))
    context.add_player(AIPlayer(seat_id=4, role=Role.WITCH, personality="steady"))
    return context


def test_build_speaking_order_skips_dead_players_and_rotates_clockwise() -> None:
    context = build_context()
    context.players[3].mark_dead()

    order = build_speaking_order(context, start_seat=2)

    assert order == [2, 4, 1]


def test_run_day_speaking_records_human_and_ai_speeches() -> None:
    context = build_context()
    thinking_events: list[tuple[int, bool]] = []

    async def human_speaker(seat_id: int) -> str:
        return f"{seat_id}号真人发言"

    async def ai_speaker(seat_id: int) -> str:
        return f"{seat_id}号AI发言"

    async def notify_thinking(seat_id: int, is_thinking: bool) -> None:
        thinking_events.append((seat_id, is_thinking))

    speeches = asyncio.run(
        run_day_speaking(
            context,
            start_seat=2,
            human_speaker=human_speaker,
            ai_speaker=ai_speaker,
            notify_thinking=notify_thinking,
        )
    )

    assert speeches == [
        "2号发言：2号AI发言",
        "3号发言：3号AI发言",
        "4号发言：4号AI发言",
        "1号发言：1号真人发言",
    ]
    assert thinking_events == [(2, True), (2, False), (4, True), (4, False)]
    assert context.public_chat_history == speeches


def test_run_day_speaking_falls_back_when_human_times_out() -> None:
    context = build_context()

    async def human_speaker(_: int) -> str:
        await asyncio.sleep(0.05)
        return "不会返回"

    async def ai_speaker(seat_id: int) -> str:
        return f"{seat_id}号AI发言"

    async def notify_thinking(_: int, __: bool) -> None:
        return None

    speeches = asyncio.run(
        run_day_speaking(
            context,
            start_seat=1,
            human_speaker=human_speaker,
            ai_speaker=ai_speaker,
            notify_thinking=notify_thinking,
            timeout_seconds=0.01,
        )
    )

    assert speeches[0] == "1号发言：过。"
