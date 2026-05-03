import asyncio
import random

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import HumanPlayer, Player
from app.engine.game_engine import GameEngine
from app.engine.night.witch_action import WitchResources
from app.engine.states.phase import GamePhase


def test_run_loop_reaches_core_phases() -> None:
    engine = GameEngine(rng=random.Random(5))

    context = asyncio.run(engine.run_loop(max_rounds=1))

    assert context.phase == GamePhase.GAME_OVER.value
    assert context.public_chat_history[0] == "游戏开始，分配身份完毕。"
    assert "天黑请闭眼。" in context.public_chat_history
    assert any(message.startswith("天亮了。") for message in context.public_chat_history)
    assert any("号发言：" in message for message in context.public_chat_history)
    assert any("玩家被放逐出局。" in message or "本轮无人出局。" in message for message in context.public_chat_history)
    assert context.public_chat_history[-1] == "夜尽未分胜负，本局暂止。"


def test_run_loop_stops_immediately_when_win_condition_is_met() -> None:
    context = GameContext()
    context.add_player(Player(seat_id=1, role=Role.VILLAGER))
    context.add_player(Player(seat_id=2, role=Role.SEER))

    engine = GameEngine()
    final_context = asyncio.run(engine.run_loop(context=context))

    assert final_context.phase == GamePhase.GAME_OVER.value
    assert final_context.public_chat_history[-1] == "狼人已全部出局，好人阵营获胜。"


def test_run_loop_executes_night_handlers_and_writes_private_logs() -> None:
    engine = GameEngine(rng=random.Random(2))

    context = asyncio.run(engine.run_loop(max_rounds=1))

    seer_seat = next(
        seat_id
        for seat_id, player in context.players.items()
        if player.role is Role.SEER
    )

    assert context.get_private_log(seer_seat)
    assert "查验结果：" in context.get_private_log(seer_seat)[0]


def test_run_loop_applies_voting_result_to_alive_state() -> None:
    engine = GameEngine(rng=random.Random(5))

    context = asyncio.run(engine.run_loop(max_rounds=1))

    alive_after_vote = context.alive_seat_ids()

    assert len(alive_after_vote) <= 8


def test_run_loop_resolves_hunter_shot_after_night_death() -> None:
    context = GameContext()
    context.add_player(Player(seat_id=1, role=Role.HUNTER))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))

    engine = GameEngine()
    final_context = asyncio.run(engine.run_loop(context=context, max_rounds=1))

    assert final_context.phase == GamePhase.GAME_OVER.value
    assert final_context.players[1].is_alive is False
    assert final_context.players[2].is_alive is False
    assert final_context.public_chat_history.index("天亮了。昨夜死亡的是 1号。") < final_context.public_chat_history.index(
        "1号猎人开枪带走了2号玩家。"
    )
    assert "1号猎人开枪带走了2号玩家。" in final_context.public_chat_history
    assert final_context.public_chat_history[-1] == "狼人已全部出局，好人阵营获胜。"


def test_run_loop_resolves_hunter_shot_after_banish() -> None:
    class HunterBanishEngine(GameEngine):
        def _choose_wolf_target(self, context: GameContext) -> int:
            return 4

        async def _build_votes(self, context: GameContext) -> dict[int, int | None]:
            return {1: 2, 2: 1, 3: 1}

    context = GameContext()
    context.add_player(Player(seat_id=1, role=Role.HUNTER))
    context.add_player(HumanPlayer(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))
    context.add_player(Player(seat_id=4, role=Role.VILLAGER))

    engine = HunterBanishEngine()
    final_context = asyncio.run(engine.run_loop(context=context, max_rounds=1))

    assert final_context.phase == GamePhase.GAME_OVER.value
    assert final_context.players[1].is_alive is False
    assert final_context.players[2].is_alive is False
    assert final_context.players[4].is_alive is False
    assert "1号玩家被放逐出局。" in final_context.public_chat_history
    assert "1号猎人开枪带走了2号玩家。" in final_context.public_chat_history
    assert final_context.public_chat_history[-1] == "狼人已全部出局，好人阵营获胜。"


def test_run_loop_blocks_hunter_shot_when_poisoned() -> None:
    class PoisonHunterEngine(GameEngine):
        def _choose_wolf_target(self, context: GameContext) -> int:
            return 4

        def _choose_witch_poison_target(
            self,
            context: GameContext,
            witch_seat: int,
            resources: WitchResources,
        ) -> int | None:
            return 1

    context = GameContext()
    context.add_player(Player(seat_id=1, role=Role.HUNTER))
    context.add_player(HumanPlayer(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.WITCH))
    context.add_player(Player(seat_id=4, role=Role.VILLAGER))

    engine = PoisonHunterEngine()
    engine._witch_resources[3] = WitchResources(has_antidote=False, has_poison=True)
    final_context = asyncio.run(engine.run_loop(context=context, max_rounds=1))

    assert final_context.phase == GamePhase.GAME_OVER.value
    assert final_context.players[1].is_alive is False
    assert final_context.players[2].is_alive is True
    assert final_context.players[4].is_alive is False
    assert final_context.public_chat_history.index("天亮了。昨夜死亡的是 4号、1号。") < final_context.public_chat_history.index(
        "1号猎人被毒死，无法开枪。"
    )
    assert "1号猎人被毒死，无法开枪。" in final_context.public_chat_history
    assert final_context.public_chat_history[-1] == "平民已全部出局，狼人阵营获胜。"


def test_run_loop_uses_default_witch_poison_after_antidote_is_spent() -> None:
    class DefaultPoisonEngine(GameEngine):
        def _choose_wolf_target(self, context: GameContext) -> int:
            return 4

    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.WOLF))
    context.add_player(Player(seat_id=2, role=Role.VILLAGER))
    context.add_player(Player(seat_id=3, role=Role.WITCH))
    context.add_player(Player(seat_id=4, role=Role.VILLAGER))

    engine = DefaultPoisonEngine()
    engine._witch_resources[3] = WitchResources(has_antidote=False, has_poison=True)
    final_context = asyncio.run(engine.run_loop(context=context, max_rounds=1))

    assert final_context.players[1].is_alive is False
    assert final_context.players[4].is_alive is False
    assert "天亮了。昨夜死亡的是 4号、1号。" in final_context.public_chat_history
    assert not any("号发言：" in message for message in final_context.public_chat_history)
    assert not any("放逐出局" in message for message in final_context.public_chat_history)
    assert final_context.public_chat_history[-1] == "狼人已全部出局，好人阵营获胜。"


def test_run_loop_increments_day_count_between_rounds() -> None:
    class MultiRoundEngine(GameEngine):
        def _choose_wolf_target(self, context: GameContext) -> int:
            return 4

        def _choose_witch_poison_target(
            self,
            context: GameContext,
            witch_seat: int,
            resources: WitchResources,
        ) -> int | None:
            return None

        async def _build_votes(self, context: GameContext) -> dict[int, int | None]:
            alive_seats = context.alive_seat_ids()
            if alive_seats == [1, 2, 3, 4]:
                return {1: 2, 2: 1, 3: 2, 4: 1}
            return {1: 2, 2: 1, 3: None}

    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.WOLF))
    context.add_player(Player(seat_id=2, role=Role.VILLAGER))
    context.add_player(Player(seat_id=3, role=Role.WITCH))
    context.add_player(Player(seat_id=4, role=Role.SEER))

    engine = MultiRoundEngine()
    final_context = asyncio.run(engine.run_loop(context=context, max_rounds=2))

    assert final_context.day_count == 3
    assert final_context.public_chat_history.count("天黑请闭眼。") == 2
