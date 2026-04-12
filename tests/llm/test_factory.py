from app.llm.factory import build_default_llm_client, build_llm_provider_from_env
from app.llm.local_provider import LocalRuleBasedProvider
from app.llm.openai_provider import OpenAICompatibleProvider


def clear_openai_env(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)


def test_build_llm_provider_from_env_defaults_to_local_provider(monkeypatch) -> None:
    clear_openai_env(monkeypatch)

    provider = build_llm_provider_from_env()

    assert isinstance(provider, LocalRuleBasedProvider)


def test_build_llm_provider_from_env_uses_openai_provider(monkeypatch) -> None:
    clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.com/v1")

    provider = build_llm_provider_from_env()

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.settings.model == "gpt-4.1-mini"
    assert provider.settings.base_url == "https://example.com/v1"


def test_build_default_llm_client_wraps_provider(monkeypatch) -> None:
    clear_openai_env(monkeypatch)

    client = build_default_llm_client()

    assert isinstance(client.client.provider, LocalRuleBasedProvider)
