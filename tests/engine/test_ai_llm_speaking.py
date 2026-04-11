import asyncio

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer, HumanPlayer, Player
from app.engine.game_engine import GameEngine
from app.llm.client import JSONModeClient
from app.llm.fallback import FallbackLLMClient
from app.llm.schemas import PromptEnvelope


class ScriptedProvider:
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
            "inner_thought": "先做轻量试探。",
            "speech_text": "2号先报个轻身份，后置位再听一轮。",
        }


def test_run_loop_uses_llm_client_for_ai_speech() -> None:
    class LLMDrivenSpeechEngine(GameEngine):
        def _choose_wolf_target(self, context: GameContext) -> int:
            return 3

        async def _human_speaker(self, seat_id: int) -> str:
            return "过。"

    provider = ScriptedProvider()
    engine = LLMDrivenSpeechEngine(
        llm_client=FallbackLLMClient(client=JSONModeClient(provider=provider)),
    )

    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.WOLF))
    context.add_player(AIPlayer(seat_id=2, role=Role.SEER, personality="谨慎分析"))
    context.add_player(Player(seat_id=3, role=Role.VILLAGER))
    context.add_player(Player(seat_id=4, role=Role.VILLAGER))

    final_context = asyncio.run(engine.run_loop(context=context, max_rounds=1))

    assert len(provider.prompts) == 1
    assert any("2号先报个轻身份，后置位再听一轮。" in message for message in final_context.public_chat_history)
