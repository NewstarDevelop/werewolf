import json

import httpx
import pytest

from app.llm.client import JSONModeError
from app.llm.openai_provider import (
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_TIMEOUT_SECONDS,
    OpenAICompatibleProvider,
    OpenAICompatibleSettings,
    load_openai_compatible_settings_from_env,
)
from app.llm.schemas import PromptEnvelope, SpeechResponse


def build_prompt() -> PromptEnvelope:
    return PromptEnvelope(
        system_prompt="系统规则",
        context_prompt="上下文信息",
        task_prompt="请给出当前发言。",
    )


def clear_openai_env(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)


def test_load_openai_compatible_settings_from_env_returns_none_when_unset(monkeypatch) -> None:
    clear_openai_env(monkeypatch)

    settings = load_openai_compatible_settings_from_env()

    assert settings is None


def test_load_openai_compatible_settings_from_env_uses_defaults(monkeypatch) -> None:
    clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")

    settings = load_openai_compatible_settings_from_env()

    assert settings is not None
    assert settings.base_url == DEFAULT_OPENAI_BASE_URL
    assert settings.timeout_seconds == DEFAULT_OPENAI_TIMEOUT_SECONDS


def test_load_openai_compatible_settings_from_env_rejects_partial_config(monkeypatch) -> None:
    clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    with pytest.raises(ValueError, match="OPENAI_MODEL"):
        load_openai_compatible_settings_from_env()


def test_load_openai_compatible_settings_from_env_rejects_invalid_timeout(monkeypatch) -> None:
    clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValueError, match="greater than 0"):
        load_openai_compatible_settings_from_env()


def test_openai_provider_posts_chat_completion_request() -> None:
    captured_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["headers"] = dict(request.headers)
        captured_request["json"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"inner_thought":"先缩视角。","speech_text":"2号先聊，我再听一轮。"}'
                            )
                        }
                    }
                ]
            },
        )

    provider = OpenAICompatibleProvider(
        settings=OpenAICompatibleSettings(
            api_key="secret",
            model="gpt-4.1-mini",
            base_url="https://example.com/v1",
        ),
        transport=httpx.MockTransport(handler),
    )

    payload = provider.complete(
        prompt=build_prompt(),
        response_schema=SpeechResponse,
    )

    assert payload == {
        "inner_thought": "先缩视角。",
        "speech_text": "2号先聊，我再听一轮。",
    }
    assert captured_request["url"] == "https://example.com/v1/chat/completions"
    headers = captured_request["headers"]
    assert isinstance(headers, dict)
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    assert normalized_headers["authorization"] == "Bearer secret"
    request_json = captured_request["json"]
    assert isinstance(request_json, dict)
    assert request_json["model"] == "gpt-4.1-mini"
    assert request_json["messages"][0]["role"] == "system"
    assert "只返回一个合法 JSON 对象" in request_json["messages"][0]["content"]


def test_openai_provider_extracts_code_fenced_json() -> None:
    provider = OpenAICompatibleProvider(
        settings=OpenAICompatibleSettings(
            api_key="secret",
            model="gpt-4.1-mini",
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    "```json\n"
                                    '{"inner_thought":"先保留身份。","speech_text":"这轮先听后置位。"}\n'
                                    "```"
                                )
                            }
                        }
                    ]
                },
            )
        ),
    )

    payload = provider.complete(
        prompt=build_prompt(),
        response_schema=SpeechResponse,
    )

    assert payload["speech_text"] == "这轮先听后置位。"


def test_openai_provider_maps_timeout_to_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    provider = OpenAICompatibleProvider(
        settings=OpenAICompatibleSettings(
            api_key="secret",
            model="gpt-4.1-mini",
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(TimeoutError):
        provider.complete(prompt=build_prompt(), response_schema=SpeechResponse)


def test_openai_provider_rejects_invalid_response_payload() -> None:
    provider = OpenAICompatibleProvider(
        settings=OpenAICompatibleSettings(
            api_key="secret",
            model="gpt-4.1-mini",
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"choices": [{"message": {"content": "not json"}}]},
            )
        ),
    )

    with pytest.raises(JSONModeError):
        provider.complete(prompt=build_prompt(), response_schema=SpeechResponse)
