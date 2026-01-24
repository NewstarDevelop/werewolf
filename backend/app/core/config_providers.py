"""AI Provider configuration management.

Extracted from config.py for better maintainability.

Provider Name Normalization Rules:
- All provider names are normalized to lowercase and stripped of whitespace
- This applies to:
  * Named providers (OPENAI, ANTHROPIC, etc.)
  * Custom providers (AI_PROVIDER_1 to AI_PROVIDER_9)
  * AI_PLAYER_MAPPING entries
  * ANALYSIS_PROVIDER configuration
- Example: "OpenAI", "openai", " OPENAI " all resolve to "openai"
- This ensures consistent lookup across all configuration sources
"""
import os
import json
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AIProviderConfig:
    """Configuration for a single AI provider."""
    name: str
    api_key: str
    base_url: Optional[str] = None
    model: str = "gpt-4o-mini"
    max_retries: int = 2
    temperature: float = 0.7
    max_tokens: int = 500
    # Rate limiting configuration
    requests_per_minute: int = 60
    max_concurrency: int = 5
    burst: int = 3

    @classmethod
    def from_env(cls, prefix: str, name: str) -> "AIProviderConfig":
        """Create config from environment variables with given prefix.

        Args:
            prefix: Environment variable prefix (e.g., "AI_PROVIDER_1")
            name: Provider name (will be normalized to lowercase)
        """
        return cls(
            name=name.lower().strip(),  # Normalize name for consistent lookup
            api_key=os.getenv(f"{prefix}_API_KEY", ""),
            base_url=os.getenv(f"{prefix}_BASE_URL") or None,
            model=os.getenv(f"{prefix}_MODEL", "gpt-4o-mini"),
            max_retries=int(os.getenv(f"{prefix}_MAX_RETRIES", "2")),
            temperature=float(os.getenv(f"{prefix}_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv(f"{prefix}_MAX_TOKENS", "500")),
            requests_per_minute=int(os.getenv(f"{prefix}_REQUESTS_PER_MINUTE", "60")),
            max_concurrency=int(os.getenv(f"{prefix}_MAX_CONCURRENCY", "5")),
            burst=int(os.getenv(f"{prefix}_BURST", "3")),
        )

    def is_valid(self) -> bool:
        """Check if this provider has valid configuration."""
        return bool(self.api_key)


@dataclass
class AIPlayerConfig:
    """Configuration for AI player to provider mapping."""
    seat_id: int
    provider_name: str


# Default models for each provider
DEFAULT_MODELS = {
    "OPENAI": "gpt-4o-mini",
    "ANTHROPIC": "claude-3-haiku-20240307",
    "DEEPSEEK": "deepseek-chat",
    "MOONSHOT": "moonshot-v1-8k",
    "QWEN": "qwen-turbo",
    "GLM": "glm-4-flash",
    "DOUBAO": "doubao-pro-4k",
    "MINIMAX": "abab6.5s-chat",
}

# Supported named providers
NAMED_PROVIDERS = ["OPENAI", "ANTHROPIC", "DEEPSEEK", "MOONSHOT", "QWEN", "GLM", "DOUBAO", "MINIMAX"]


class ProviderManager:
    """Manages AI provider configurations and player mappings."""

    def __init__(self):
        self._providers: dict[str, AIProviderConfig] = {}
        self._player_mappings: dict[int, str] = {}

    def load_providers(
        self,
        openai_api_key: str,
        openai_base_url: Optional[str],
        llm_model: str,
        llm_max_retries: int
    ) -> None:
        """Load AI provider configurations from environment."""
        # Default provider (OpenAI)
        default_provider = AIProviderConfig(
            name="default",
            api_key=openai_api_key,
            base_url=openai_base_url,
            model=llm_model,
            max_retries=llm_max_retries,
            requests_per_minute=int(os.getenv("DEFAULT_REQUESTS_PER_MINUTE", "60")),
            max_concurrency=int(os.getenv("DEFAULT_MAX_CONCURRENCY", "5")),
            burst=int(os.getenv("DEFAULT_BURST", "3")),
        )
        if default_provider.is_valid():
            self._providers["default"] = default_provider

        # Load named providers
        for provider_name in NAMED_PROVIDERS:
            api_key = os.getenv(f"{provider_name}_API_KEY")
            if api_key:
                provider = AIProviderConfig(
                    name=provider_name.lower(),
                    api_key=api_key,
                    base_url=os.getenv(f"{provider_name}_BASE_URL") or None,
                    model=os.getenv(f"{provider_name}_MODEL", DEFAULT_MODELS.get(provider_name, "gpt-4o-mini")),
                    max_retries=int(os.getenv(f"{provider_name}_MAX_RETRIES", "2")),
                    temperature=float(os.getenv(f"{provider_name}_TEMPERATURE", "0.7")),
                    max_tokens=int(os.getenv(f"{provider_name}_MAX_TOKENS", "500")),
                    requests_per_minute=int(os.getenv(f"{provider_name}_REQUESTS_PER_MINUTE", "60")),
                    max_concurrency=int(os.getenv(f"{provider_name}_MAX_CONCURRENCY", "5")),
                    burst=int(os.getenv(f"{provider_name}_BURST", "5")),
                )
                self._providers[provider_name.lower()] = provider

        # Load custom providers (AI_PROVIDER_1 to AI_PROVIDER_9)
        for i in range(1, 10):
            prefix = f"AI_PROVIDER_{i}"
            name = os.getenv(f"{prefix}_NAME")
            if name:
                provider = AIProviderConfig.from_env(prefix, name)
                if provider.is_valid():
                    # Store using normalized name (already normalized in from_env)
                    self._providers[provider.name] = provider

        # Load per-player providers (AI_PLAYER_2 to AI_PLAYER_9)
        for seat_id in range(2, 10):
            prefix = f"AI_PLAYER_{seat_id}"
            api_key = os.getenv(f"{prefix}_API_KEY")
            if api_key:
                provider_name = f"player_{seat_id}"
                provider = AIProviderConfig(
                    name=provider_name,
                    api_key=api_key,
                    base_url=os.getenv(f"{prefix}_BASE_URL") or None,
                    model=os.getenv(f"{prefix}_MODEL", "gpt-4o-mini"),
                    max_retries=int(os.getenv(f"{prefix}_MAX_RETRIES", "2")),
                    temperature=float(os.getenv(f"{prefix}_TEMPERATURE", "0.7")),
                    max_tokens=int(os.getenv(f"{prefix}_MAX_TOKENS", "500")),
                    requests_per_minute=int(os.getenv(f"{prefix}_REQUESTS_PER_MINUTE", "60")),
                    max_concurrency=int(os.getenv(f"{prefix}_MAX_CONCURRENCY", "5")),
                    burst=int(os.getenv(f"{prefix}_BURST", "5")),
                )
                if provider.is_valid():
                    self._providers[provider_name] = provider

    def load_player_mappings(self) -> None:
        """Load AI player to provider mappings with correct priority."""
        # Priority 1: Auto-map players with specific provider configs
        for seat_id in range(2, 10):
            provider_name = f"player_{seat_id}"
            if provider_name in self._providers:
                self._player_mappings[seat_id] = provider_name

        # Priority 2: JSON batch mapping
        mapping_json = os.getenv("AI_PLAYER_MAPPING")
        if mapping_json:
            try:
                mapping = json.loads(mapping_json)
                for seat_str, provider in mapping.items():
                    seat_id = int(seat_str)
                    # MAJOR FIX: Normalize provider name to lowercase for consistent lookup
                    provider_normalized = provider.lower().strip()
                    if provider_normalized in self._providers:
                        self._player_mappings[seat_id] = provider_normalized
                    else:
                        logger.warning(f"AI_PLAYER_MAPPING: provider '{provider}' not found for seat {seat_id}")
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse AI_PLAYER_MAPPING: {e}")

        # Priority 3: Individual mapping per seat
        for seat_id in range(1, 13):
            provider = os.getenv(f"AI_PLAYER_{seat_id}_PROVIDER")
            if provider:
                # MINOR FIX: Normalize provider name to lowercase for consistency
                provider = provider.lower().strip()
                if provider in self._providers:
                    self._player_mappings[seat_id] = provider
                else:
                    logger.warning(
                        f"AI_PLAYER_{seat_id}_PROVIDER: provider '{provider}' not found, "
                        f"falling back to default or auto-mapped provider"
                    )

    def get_provider(self, name: str) -> Optional[AIProviderConfig]:
        """Get provider configuration by name."""
        return self._providers.get(name)

    def get_provider_for_player(self, seat_id: int) -> Optional[AIProviderConfig]:
        """Get provider configuration for a specific player seat."""
        provider_name = self._player_mappings.get(seat_id, "default")
        return self._providers.get(provider_name) or self._providers.get("default")

    def get_all_providers(self) -> dict[str, AIProviderConfig]:
        """Get all configured providers."""
        return self._providers.copy()

    def get_player_mappings(self) -> dict[int, str]:
        """Get all player to provider mappings."""
        return self._player_mappings.copy()

    def log_summary(self) -> None:
        """Log configuration summary for debugging."""
        logger.info(f"AI Configuration loaded: {len(self._providers)} providers configured")

        burst_warnings = []
        for name, provider in self._providers.items():
            logger.info(f"  Provider '{name}': model={provider.model}, base_url={provider.base_url or 'default'}")
            if provider.burst < provider.max_concurrency:
                burst_warnings.append(
                    f"Provider '{name}': burst ({provider.burst}) < max_concurrency ({provider.max_concurrency}). "
                    f"This may cause unexpected throttling."
                )

        if burst_warnings:
            logger.warning("=" * 50)
            logger.warning("Rate Limiter Configuration Warnings:")
            for warning in burst_warnings:
                logger.warning(f"  ⚠️  {warning}")
            logger.warning("=" * 50)

        if self._player_mappings:
            logger.info("Player to provider mappings:")
            for seat_id in sorted(self._player_mappings.keys()):
                provider_name = self._player_mappings[seat_id]
                provider = self._providers.get(provider_name)
                model_info = f" (model: {provider.model})" if provider else ""
                logger.info(f"  Seat {seat_id} -> {provider_name}{model_info}")
        else:
            logger.info("No explicit player mappings - all players use default provider")
