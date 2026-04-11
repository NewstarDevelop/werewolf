import asyncio
from collections.abc import Awaitable, Callable

from app.domain.game_context import GameContext
from app.domain.player import AIPlayer, HumanPlayer

HumanSpeaker = Callable[[int], Awaitable[str]]
AISpeaker = Callable[[int], Awaitable[str]]
ThinkingNotifier = Callable[[int, bool], Awaitable[None]]


def build_speaking_order(context: GameContext, *, start_seat: int) -> list[int]:
    alive_seats = context.alive_seat_ids()
    if start_seat not in alive_seats:
        raise ValueError("start seat must be alive")

    start_index = alive_seats.index(start_seat)
    return alive_seats[start_index:] + alive_seats[:start_index]


async def run_day_speaking(
    context: GameContext,
    *,
    start_seat: int,
    human_speaker: HumanSpeaker,
    ai_speaker: AISpeaker,
    notify_thinking: ThinkingNotifier,
    timeout_seconds: float = 60.0,
) -> list[str]:
    speeches: list[str] = []

    for seat_id in build_speaking_order(context, start_seat=start_seat):
        player = context.players[seat_id]

        if isinstance(player, HumanPlayer):
            try:
                speech = await asyncio.wait_for(human_speaker(seat_id), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                speech = "过。"
        elif isinstance(player, AIPlayer):
            await notify_thinking(seat_id, True)
            speech = await ai_speaker(seat_id)
            await notify_thinking(seat_id, False)
        else:
            speech = await ai_speaker(seat_id)

        record = f"{seat_id}号发言：{speech}"
        speeches.append(record)
        context.add_public_message(record)

    return speeches
