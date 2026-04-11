from app.domain.game_context import GameContext
from app.engine.day.dead_last_words import announce_deaths_and_last_words


def test_first_night_dead_players_get_last_words() -> None:
    context = GameContext(day_count=1)
    context.mark_killed_tonight(3, cause="wolf")
    context.mark_killed_tonight(5, cause="poison")

    announcement = announce_deaths_and_last_words(context)

    assert announcement.message == "天亮了。昨夜死亡的是 3号、5号。"
    assert announcement.eligible_last_words == [3, 5]
    assert context.public_chat_history[-1] == announcement.message


def test_non_first_night_deaths_do_not_get_last_words() -> None:
    context = GameContext(day_count=2)
    context.mark_killed_tonight(4, cause="wolf")

    announcement = announce_deaths_and_last_words(context)

    assert announcement.message == "天亮了。昨夜死亡的是 4号。"
    assert announcement.eligible_last_words == []


def test_banished_player_always_gets_last_words() -> None:
    context = GameContext(day_count=3)

    announcement = announce_deaths_and_last_words(context, banished_seat=6)

    assert announcement.message == "天亮了。昨夜是平安夜。"
    assert announcement.eligible_last_words == [6]
