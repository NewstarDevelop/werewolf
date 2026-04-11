from dataclasses import dataclass

from app.domain.game_context import GameContext


@dataclass(slots=True, kw_only=True)
class DeathAnnouncement:
    message: str
    eligible_last_words: list[int]


def announce_deaths_and_last_words(
    context: GameContext,
    *,
    banished_seat: int | None = None,
) -> DeathAnnouncement:
    dead_list = list(context.killed_tonight)
    eligible_last_words: list[int] = []

    if dead_list:
        dead_text = "、".join(f"{seat}号" for seat in dead_list)
        message = f"天亮了。昨夜死亡的是 {dead_text}。"
        if context.day_count == 1:
            eligible_last_words.extend(dead_list)
    else:
        message = "天亮了。昨夜是平安夜。"

    if banished_seat is not None:
        eligible_last_words.append(banished_seat)

    context.add_public_message(message)
    return DeathAnnouncement(message=message, eligible_last_words=eligible_last_words)
