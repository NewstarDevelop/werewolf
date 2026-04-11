import asyncio

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer, HumanPlayer, Player
from app.engine.game_engine import GameEngine
from app.llm.client import JSONModeClient
from app.llm.fallback import FallbackLLMClient
from app.llm.schemas import PromptEnvelope


class ScriptedVoteProvider:
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
            "inner_thought": "2号像狼，先把票挂过去。",
            "vote_target": 2,
        }


def test_build_votes_uses_llm_client_for_ai_vote() -> None:
    provider = ScriptedVoteProvider()
    engine = GameEngine(
        llm_client=FallbackLLMClient(client=JSONModeClient(provider=provider)),
    )

    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.VILLAGER))
    context.add_player(Player(seat_id=2, role=Role.WOLF))
    context.add_player(AIPlayer(seat_id=3, role=Role.SEER, personality="谨慎分析"))

    votes = asyncio.run(engine._build_votes(context))

    assert votes == {1: 2, 2: 1, 3: 2}
    assert len(provider.prompts) == 1
