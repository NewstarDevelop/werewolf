import asyncio

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer, HumanPlayer, Player
from app.engine.day.day_speaking import run_day_speaking
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

    assert any("发言" in prompt.task_prompt for prompt in provider.prompts)
    assert any("2号先报个轻身份，后置位再听一轮。" in message for message in final_context.public_chat_history)


def test_ai_speech_prompt_uses_human_speech_without_requesting_human_seat() -> None:
    provider = ScriptedProvider()
    engine = GameEngine(
        llm_client=FallbackLLMClient(client=JSONModeClient(provider=provider)),
    )
    context = GameContext(phase="DAY_SPEAKING")
    context.add_player(HumanPlayer(seat_id=1, role=Role.SEER))
    context.add_player(AIPlayer(seat_id=2, role=Role.WOLF, personality="谨慎分析"))

    async def human_speaker(seat_id: int) -> str:
        assert seat_id == 1
        return "我是预言家，昨晚查了2号。"

    async def notify_thinking(_: int, __: bool) -> None:
        return None

    asyncio.run(
        run_day_speaking(
            context,
            start_seat=1,
            human_speaker=human_speaker,
            ai_speaker=lambda seat_id: engine._llm_speaker(context, seat_id),
            notify_thinking=notify_thinking,
        )
    )

    assert len(provider.prompts) == 1
    prompt = provider.prompts[0]
    assert "现在轮到 2号 发言" in prompt.task_prompt
    assert "现在轮到 1号 发言" not in prompt.task_prompt
    assert "1号发言：我是预言家，昨晚查了2号。" in prompt.context_prompt


def test_llm_speaker_delegates_human_seats_without_prompting_llm() -> None:
    class HumanSpeechEngine(GameEngine):
        async def _human_speaker(self, seat_id: int) -> str:
            assert seat_id == 1
            return "真人自己发言。"

    provider = ScriptedProvider()
    engine = HumanSpeechEngine(
        llm_client=FallbackLLMClient(client=JSONModeClient(provider=provider)),
    )
    context = GameContext()
    context.add_player(HumanPlayer(seat_id=1, role=Role.SEER))

    speech = asyncio.run(engine._llm_speaker(context, 1))

    assert speech == "真人自己发言。"
    assert provider.prompts == []
