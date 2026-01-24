"""AI Analysis configuration.

Extracted from config.py for better maintainability.
"""
import os
import logging
from typing import Optional
from .config_providers import AIProviderConfig

logger = logging.getLogger(__name__)


class AnalysisConfig:
    """Configuration for AI game analysis."""

    def __init__(self, default_model: str):
        self.ANALYSIS_PROVIDER: Optional[str] = os.getenv("ANALYSIS_PROVIDER") or None
        self.ANALYSIS_MODEL: str = os.getenv("ANALYSIS_MODEL", default_model)
        self.ANALYSIS_MAX_TOKENS: int = int(os.getenv("ANALYSIS_MAX_TOKENS", "4000"))
        self.ANALYSIS_TEMPERATURE: float = float(os.getenv("ANALYSIS_TEMPERATURE", "0.7"))
        self.ANALYSIS_MODE: str = os.getenv("ANALYSIS_MODE", "comprehensive")
        self.ANALYSIS_LANGUAGE: str = os.getenv("ANALYSIS_LANGUAGE", "auto")
        self.ANALYSIS_CACHE_ENABLED: bool = os.getenv("ANALYSIS_CACHE_ENABLED", "true").lower() == "true"

    def get_provider(self, providers: dict[str, AIProviderConfig]) -> Optional[AIProviderConfig]:
        """Get provider configuration for game analysis.

        Priority:
        1. Dedicated ANALYSIS_PROVIDER if specified
        2. Default provider with analysis settings
        3. None (will use fallback mode)
        """
        # Priority 1: Dedicated ANALYSIS_PROVIDER
        if self.ANALYSIS_PROVIDER:
            # MAJOR FIX: Normalize provider name to lowercase for consistent lookup
            provider_key = self.ANALYSIS_PROVIDER.lower().strip()
            provider = providers.get(provider_key)
            if provider and provider.is_valid():
                return AIProviderConfig(
                    name=f"analysis_{provider.name}",
                    api_key=provider.api_key,
                    base_url=provider.base_url,
                    model=self.ANALYSIS_MODEL,
                    max_retries=provider.max_retries,
                    temperature=self.ANALYSIS_TEMPERATURE,
                    max_tokens=self.ANALYSIS_MAX_TOKENS,
                )

        # Priority 2: Default provider with analysis settings
        default = providers.get("default")
        if default and default.is_valid():
            return AIProviderConfig(
                name="analysis_default",
                api_key=default.api_key,
                base_url=default.base_url,
                model=self.ANALYSIS_MODEL,
                max_retries=default.max_retries,
                temperature=self.ANALYSIS_TEMPERATURE,
                max_tokens=self.ANALYSIS_MAX_TOKENS,
            )

        logger.warning(
            "No valid AI provider configured for analysis. "
            "Analysis will use fallback mode (basic statistics only)."
        )
        return None

    def validate(self, providers: dict[str, AIProviderConfig]) -> tuple[bool, list[str]]:
        """Validate analysis configuration.

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        if not providers:
            errors.append("No AI provider configured. Set OPENAI_API_KEY or other provider.")

        if self.ANALYSIS_PROVIDER:
            provider_key = self.ANALYSIS_PROVIDER.lower()
            if provider_key not in providers:
                errors.append(f"ANALYSIS_PROVIDER '{self.ANALYSIS_PROVIDER}' not found.")
            elif not providers[provider_key].is_valid():
                errors.append(f"ANALYSIS_PROVIDER '{self.ANALYSIS_PROVIDER}' has invalid configuration.")

        valid_modes = ["comprehensive", "quick", "custom"]
        if self.ANALYSIS_MODE not in valid_modes:
            errors.append(f"ANALYSIS_MODE must be one of {valid_modes}, got '{self.ANALYSIS_MODE}'")

        valid_languages = ["auto", "zh", "en"]
        if self.ANALYSIS_LANGUAGE not in valid_languages:
            errors.append(f"ANALYSIS_LANGUAGE must be one of {valid_languages}, got '{self.ANALYSIS_LANGUAGE}'")

        return (len(errors) == 0, errors)

    def log_summary(self, providers: dict[str, AIProviderConfig]) -> None:
        """Log analysis configuration summary."""
        logger.info("=" * 50)
        logger.info("Analysis Configuration:")
        logger.info(f"  Mode: {self.ANALYSIS_MODE}")
        logger.info(f"  Language: {self.ANALYSIS_LANGUAGE}")
        logger.info(f"  Model: {self.ANALYSIS_MODEL}")
        logger.info(f"  Max Tokens: {self.ANALYSIS_MAX_TOKENS}")
        logger.info(f"  Cache Enabled: {self.ANALYSIS_CACHE_ENABLED}")

        analysis_provider = self.get_provider(providers)
        if analysis_provider:
            logger.info(f"  Provider: {analysis_provider.name} (model: {analysis_provider.model})")
        else:
            logger.warning("  Provider: None - Analysis will use fallback mode")

        is_valid, errors = self.validate(providers)
        if not is_valid:
            logger.warning("Analysis configuration issues:")
            for error in errors:
                logger.warning(f"  - {error}")
