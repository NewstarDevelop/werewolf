from collections.abc import Sequence

from app.llm.client import JSONModeClient, ProviderRequestError
from app.llm.fallback import FallbackLLMClient
from app.llm.schemas import PromptEnvelope


class ScriptedProvider:
    def __init__(self, responses: Sequence[object]) -> None:
        self._responses = list(responses)
        self.prompts: list[PromptEnvelope] = []

    def complete(
        self,
        *,
        prompt: PromptEnvelope,
        response_schema: type[object],
    ) -> object:
        self.prompts.append(prompt)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def build_prompt() -> PromptEnvelope:
    return PromptEnvelope(
        system_prompt="系统规则",
        context_prompt="上下文",
        task_prompt="当前任务",
    )


def test_timeout_then_retry_returns_successful_speech() -> None:
    provider = ScriptedProvider(
        [
            TimeoutError("request timed out"),
            {
                "inner_thought": "补发一次。",
                "speech_text": "我先保留判断，继续听后面玩家怎么聊。",
            },
        ]
    )
    client = FallbackLLMClient(client=JSONModeClient(provider=provider))

    response = client.request_speech(prompt=build_prompt())

    assert response.speech_text.startswith("我先保留")
    assert len(provider.prompts) == 2
    assert provider.prompts[1].task_prompt == provider.prompts[0].task_prompt


def test_retryable_provider_error_retries_without_mutating_prompt() -> None:
    provider = ScriptedProvider(
        [
            ProviderRequestError("server error", status_code=500, retryable=True),
            {
                "inner_thought": "第二次请求成功。",
                "speech_text": "我先继续听后置位怎么聊。",
            },
        ]
    )
    client = FallbackLLMClient(client=JSONModeClient(provider=provider))

    response = client.request_speech(prompt=build_prompt())

    assert response.speech_text == "我先继续听后置位怎么聊。"
    assert len(provider.prompts) == 2
    assert provider.prompts[1].task_prompt == provider.prompts[0].task_prompt


def test_invalid_json_falls_back_to_default_speech() -> None:
    provider = ScriptedProvider(
        [
            '{"inner_thought":"第一次坏 JSON"',
            '{"inner_thought":"第二次也坏 JSON"',
            '{"inner_thought":"第三次仍然坏 JSON"',
        ]
    )
    client = FallbackLLMClient(client=JSONModeClient(provider=provider))

    response = client.request_speech(prompt=build_prompt())

    assert response.speech_text == "我没什么线索，过。"
    assert len(provider.prompts) == 3


def test_illegal_vote_target_retries_with_allowed_targets_hint() -> None:
    provider = ScriptedProvider(
        [
            {
                "inner_thought": "先随便投一个。",
                "vote_target": 9,
            },
            {
                "inner_thought": "改成合法目标。",
                "vote_target": 4,
            },
        ]
    )
    client = FallbackLLMClient(client=JSONModeClient(provider=provider))

    response = client.request_vote(prompt=build_prompt(), allowed_targets=[3, 4, 5])

    assert response.vote_target == 4
    assert len(provider.prompts) == 2
    assert "只能在 [3, 4, 5] 中选择" in provider.prompts[1].task_prompt


def test_illegal_targeted_action_falls_back_to_no_action() -> None:
    provider = ScriptedProvider(
        [
            {
                "inner_thought": "我要毒 9 号。",
                "target": 9,
                "use_poison": True,
            },
            {
                "inner_thought": "还是毒 9 号。",
                "target": 9,
                "use_poison": True,
            },
            {
                "inner_thought": "继续毒 9 号。",
                "target": 9,
                "use_poison": True,
            },
        ]
    )
    client = FallbackLLMClient(client=JSONModeClient(provider=provider))

    response = client.request_targeted_action(prompt=build_prompt(), allowed_targets=[2, 3])

    assert response.target is None
    assert response.use_poison is False
