"""Provider configuration and manager."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import get_settings


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""

    provider: str  # "mock" | "openai" | "anthropic" | "deepseek" | "custom"
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    temperature: float = 0.7
    max_tokens: int = 1024

    # Preset configurations for known providers
    KNOWN_PRESETS: dict[str, dict] = field(default_factory=lambda: {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o-mini",
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com/v1",
            "default_model": "claude-sonnet-4-20250514",
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "default_model": "deepseek-chat",
        },
    })

    def resolve_base_url(self) -> str:
        """Resolve the base URL for this provider."""
        if self.base_url:
            return self.base_url
        preset = self.KNOWN_PRESETS.get(self.provider)
        if preset:
            return preset["base_url"]
        raise ValueError(f"Unknown provider '{self.provider}' and no base_url specified")

    def resolve_model(self) -> str:
        """Resolve the model name, falling back to provider defaults."""
        if self.model:
            return self.model
        preset = self.KNOWN_PRESETS.get(self.provider)
        if preset:
            return preset["default_model"]
        raise ValueError(f"No model specified for provider '{self.provider}'")

    def resolve_api_key(self) -> str:
        """Resolve the API key from config or environment."""
        if self.api_key:
            return self.api_key
        # Fall back to settings-based key
        settings = get_settings()
        key_map = {
            "openai": settings.LLM_DEFAULT_API_KEY,
            "anthropic": settings.LLM_DEFAULT_API_KEY,
            "deepseek": settings.LLM_DEFAULT_API_KEY,
            "custom": settings.LLM_DEFAULT_API_KEY,
        }
        key = key_map.get(self.provider, "")
        if not key:
            raise ValueError(f"No API key configured for provider '{self.provider}'")
        return key


class ProviderManager:
    """Manages provider configurations and creates LLM clients.

    Reads global defaults from Settings and creates per-seat
    LLMClient instances on demand.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def get_default_config(self) -> ProviderConfig:
        """Get the global default provider config from settings."""
        provider = self._settings.LLM_DEFAULT_PROVIDER or "mock"
        if provider == "mock":
            return ProviderConfig(provider="mock")

        # Try per-provider settings first
        provider_key = provider.upper()
        api_key = getattr(self._settings, f"LLM_{provider_key}_API_KEY", "") or self._settings.LLM_DEFAULT_API_KEY
        model = getattr(self._settings, f"LLM_{provider_key}_MODEL", "") or self._settings.LLM_DEFAULT_MODEL
        base_url = getattr(self._settings, f"LLM_{provider_key}_BASE_URL", "") or self._settings.LLM_DEFAULT_BASE_URL

        return ProviderConfig(
            provider=provider,
            model=model or None,
            base_url=base_url or None,
            api_key=api_key or None,
            temperature=self._settings.LLM_DEFAULT_TEMPERATURE,
            max_tokens=self._settings.LLM_DEFAULT_MAX_TOKENS,
        )

    def resolve_config(
        self,
        provider: str | None = None,
        model: str | None = None,
        ai_config: dict | None = None,
    ) -> ProviderConfig:
        """Resolve a per-seat AI config, merging with global defaults.

        Args:
            provider: Provider name from RoomPlayer
            model: Model name from RoomPlayer
            ai_config: Extra config dict from RoomPlayer (base_url, etc.)
        """
        # No provider or "mock" → use mock
        if not provider or provider == "mock":
            return ProviderConfig(provider="mock")

        # Merge: explicit per-seat overrides global defaults
        defaults = self.get_default_config()

        resolved_provider = provider or defaults.provider
        resolved_model = model or defaults.model
        resolved_base_url = (ai_config or {}).get("base_url") or defaults.base_url
        resolved_api_key = (ai_config or {}).get("api_key") or defaults.api_key
        resolved_temperature = (ai_config or {}).get("temperature", defaults.temperature)
        resolved_max_tokens = (ai_config or {}).get("max_tokens", defaults.max_tokens)

        return ProviderConfig(
            provider=resolved_provider,
            model=resolved_model,
            base_url=resolved_base_url,
            api_key=resolved_api_key,
            temperature=resolved_temperature,
            max_tokens=resolved_max_tokens,
        )

    def create_client(self, config: ProviderConfig):
        """Create an LLM client for the given config.

        Returns the appropriate client instance based on provider type.
        """
        if config.provider == "mock":
            from app.services.llm.mock import MockClient
            return MockClient()

        from app.services.llm.openai_compat import OpenAICompatClient
        return OpenAICompatClient(
            base_url=config.resolve_base_url(),
            api_key=config.resolve_api_key(),
            model=config.resolve_model(),
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )


# Singleton
provider_manager = ProviderManager()
