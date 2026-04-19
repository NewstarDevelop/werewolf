import json

import httpx
import pytest

from app.llm.client import JSONModeError, ProviderRequestError
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
        system_prompt="system",
        context_prompt="context",
        task_prompt="task",
    )


def clear_openai_env(monkeypatch) -> None:
    for name in (
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OPENAI_BASE_URL",
        "OPENAI_TIMEOUT_SECONDS",
        "STITCH_API_KEY",
        "STITCH_MODEL",
        "STITCH_BASE_URL",
        "STITCH_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


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


def test_load_openai_compatible_settings_from_env_supports_stitch_aliases(monkeypatch) -> None:
    clear_openai_env(monkeypatch)
    monkeypatch.setenv("STITCH_API_KEY", "secret")
    monkeypatch.setenv("STITCH_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("STITCH_BASE_URL", "https://example.com/v1")

    settings = load_openai_compatible_settings_from_env()

    assert settings is not None
    assert settings.api_key == "secret"
    assert settings.model == "gpt-4.1-mini"
    assert settings.base_url == "https://example.com/v1"


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
                            "content": '{"inner_thought":"observe first","speech_text":"I want to hear more."}',
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
        "inner_thought": "observe first",
        "speech_text": "I want to hear more.",
    }
    assert captured_request["url"] == "https://example.com/v1/chat/completions"
    headers = captured_request["headers"]
    assert isinstance(headers, dict)
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    assert normalized_headers["authorization"] == "Bearer secret"
    request_json = captured_request["json"]
    assert isinstance(request_json, dict)
    assert request_json["model"] == "gpt-4.1-mini"
    assert request_json["response_format"] == {"type": "json_object"}
    assert request_json["stream"] is False
    assert request_json["messages"][0]["role"] == "system"


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
                                    '{"inner_thought":"hide role","speech_text":"I will listen first."}\n'
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

    assert payload["speech_text"] == "I will listen first."


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


def test_openai_provider_marks_server_error_as_retryable() -> None:
    provider = OpenAICompatibleProvider(
        settings=OpenAICompatibleSettings(
            api_key="secret",
            model="gpt-4.1-mini",
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                500,
                json={"error": {"message": "upstream overloaded"}},
            )
        ),
    )

    with pytest.raises(ProviderRequestError) as exc_info:
        provider.complete(prompt=build_prompt(), response_schema=SpeechResponse)

    assert exc_info.value.status_code == 500
    assert exc_info.value.retryable is True


def test_openai_provider_retries_without_response_format_for_compatible_backends() -> None:
    request_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        request_payloads.append(payload)
        if "response_format" in payload:
            return httpx.Response(
                400,
                json={"error": {"message": "response_format json_object is unsupported"}},
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"inner_thought":"compat fallback applied","speech_text":"real provider response"}',
                        }
                    }
                ]
            },
        )

    provider = OpenAICompatibleProvider(
        settings=OpenAICompatibleSettings(
            api_key="secret",
            model="gpt-4.1-mini",
        ),
        transport=httpx.MockTransport(handler),
    )

    payload = provider.complete(
        prompt=build_prompt(),
        response_schema=SpeechResponse,
    )

    assert payload["speech_text"] == "real provider response"
    assert len(request_payloads) == 2
    assert request_payloads[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in request_payloads[1]
