import pytest
from pydantic import ValidationError

from app.llm.client import JSONModeClient, JSONModeError
from app.llm.schemas import PromptEnvelope, SpeechResponse


class FakeProvider:
    def __init__(self, response: str | dict[str, object]) -> None:
        self.response = response
        self.calls: list[tuple[PromptEnvelope, type[object]]] = []

    def complete(
        self,
        *,
        prompt: PromptEnvelope,
        response_schema: type[object],
    ) -> str | dict[str, object]:
        self.calls.append((prompt, response_schema))
        return self.response


def build_prompt() -> PromptEnvelope:
    return PromptEnvelope(
        system_prompt="系统规则",
        context_prompt="上下文",
        task_prompt="当前任务",
    )


def test_request_parses_json_string_with_schema() -> None:
    provider = FakeProvider(
        '{"inner_thought":"我要伪装成好人。","speech_text":"4号这轮视角有问题，我建议继续听后置位发言。"}'
    )
    client = JSONModeClient(provider=provider)

    response = client.request_speech(prompt=build_prompt())

    assert isinstance(response, SpeechResponse)
    assert response.speech_text.startswith("4号")
    assert provider.calls[0][1] is SpeechResponse


def test_request_accepts_mapping_payload() -> None:
    provider = FakeProvider(
        {
            "inner_thought": "信息不够，先弃票。",
            "vote_target": 0,
        }
    )
    client = JSONModeClient(provider=provider)

    response = client.request_vote(prompt=build_prompt())

    assert response.vote_target == 0


def test_request_rejects_invalid_json_text() -> None:
    provider = FakeProvider('{"inner_thought":"遗漏了闭合"')
    client = JSONModeClient(provider=provider)

    with pytest.raises(JSONModeError):
        client.request_speech(prompt=build_prompt())


def test_request_rejects_json_array_payload() -> None:
    provider = FakeProvider('[{"inner_thought":"不合法"}]')
    client = JSONModeClient(provider=provider)

    with pytest.raises(JSONModeError):
        client.request_speech(prompt=build_prompt())


def test_request_surfaces_schema_validation_errors() -> None:
    provider = FakeProvider(
        {
            "inner_thought": "我要长篇输出。",
            "speech_text": "",
        }
    )
    client = JSONModeClient(provider=provider)

    with pytest.raises(ValidationError):
        client.request_speech(prompt=build_prompt())
