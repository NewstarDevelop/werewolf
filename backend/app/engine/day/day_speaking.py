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
    timeout_seconds: float | None = 60.0,
) -> list[str]:
    speeches: list[str] = []

    for seat_id in build_speaking_order(context, start_seat=start_seat):
        player = context.players[seat_id]

        if isinstance(player, HumanPlayer):
            if timeout_seconds is None:
                speech = await human_speaker(seat_id)
            else:
                try:
                    speech = await asyncio.wait_for(human_speaker(seat_id), timeout=timeout_seconds)
                except asyncio.TimeoutError:
                    speech = "过。"
        elif isinstance(player, AIPlayer):
            await notify_thinking(seat_id, True)
            try:
                speech = await ai_speaker(seat_id)
            finally:
                await notify_thinking(seat_id, False)
        else:
            speech = await ai_speaker(seat_id)

        record = f"{seat_id}号发言：{speech}"
        speeches.append(record)
        if isinstance(player, AIPlayer):
            player.remember(f"我白天公开发言：{speech}")
        context.add_public_message(
            record,
            message_kind="speech",
            event_type="SPEECH",
            actor_seat=seat_id,
        )
        # Let websocket bridge tasks publish this speech before the next
        # speaker starts a potentially blocking AI request.
        await asyncio.sleep(0)

    return speeches
