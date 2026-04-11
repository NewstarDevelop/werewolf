import asyncio

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer, Player
from app.engine.game_engine import GameEngine
from app.llm.client import JSONModeClient
from app.llm.fallback import FallbackLLMClient
from app.llm.schemas import PromptEnvelope


class ScriptedTargetProvider:
    def __init__(self) -> None:
        self.prompts: list[PromptEnvelope] = []

    def complete(
        self,
        *,
        prompt: PromptEnvelope,
        response_schema: type[object],
    ) -> dict[str, object]:
        self.prompts.append(prompt)
        return {
            "inner_thought": "优先验 3 号。",
            "target": 3,
            "use_antidote": False,
            "use_poison": False,
        }


def test_select_seer_target_uses_llm_client_for_ai_player() -> None:
    provider = ScriptedTargetProvider()
    engine = GameEngine(
        llm_client=FallbackLLMClient(client=JSONModeClient(provider=provider)),
    )

    context = GameContext()
    context.add_player(AIPlayer(seat_id=1, role=Role.SEER, personality="谨慎分析"))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))

    target = asyncio.run(
        engine._select_seer_target(
            context,
            seer_seat=1,
            allowed_targets=[2, 3],
        ),
    )

    assert target == 3
    assert len(provider.prompts) == 1
