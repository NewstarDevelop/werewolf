import asyncio

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer, Player
from app.engine.game_engine import GameEngine
from app.engine.night.witch_action import WitchResources
from app.llm.client import JSONModeClient
from app.llm.fallback import FallbackLLMClient
from app.llm.schemas import PromptEnvelope


class ScriptedWitchProvider:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.prompts: list[PromptEnvelope] = []

    def complete(
        self,
        *,
        prompt: PromptEnvelope,
        response_schema: type[object],
    ) -> dict[str, object]:
        self.prompts.append(prompt)
        return self.response


def test_select_witch_action_uses_llm_client_for_save() -> None:
    provider = ScriptedWitchProvider(
        {
            "inner_thought": "先把人救起来。",
            "target": None,
            "use_antidote": True,
            "use_poison": False,
        }
    )
    engine = GameEngine(
        llm_client=FallbackLLMClient(client=JSONModeClient(provider=provider)),
    )

    context = GameContext()
    context.add_player(AIPlayer(seat_id=1, role=Role.WITCH, personality="谨慎分析"))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))

    action = asyncio.run(
        engine._select_witch_action(
            context,
            witch_seat=1,
            resources=WitchResources(),
            save_candidates=[3],
            poison_candidates=[2],
        ),
    )

    assert action == (3, None)
    assert len(provider.prompts) == 1


def test_select_witch_action_uses_llm_client_for_poison() -> None:
    provider = ScriptedWitchProvider(
        {
            "inner_thought": "今晚直接毒 2 号。",
            "target": 2,
            "use_antidote": False,
            "use_poison": True,
        }
    )
    engine = GameEngine(
        llm_client=FallbackLLMClient(client=JSONModeClient(provider=provider)),
    )

    context = GameContext()
    context.add_player(AIPlayer(seat_id=1, role=Role.WITCH, personality="谨慎分析"))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))

    action = asyncio.run(
        engine._select_witch_action(
            context,
            witch_seat=1,
            resources=WitchResources(has_antidote=False, has_poison=True),
            save_candidates=[],
            poison_candidates=[2, 3],
        ),
    )

    assert action == (None, 2)
    assert len(provider.prompts) == 1
