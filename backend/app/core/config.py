"""Application configuration with multi-AI provider support."""
import os
import json
import logging
from typing import Optional
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Smart .env loading with fallback support
# Priority: environment variables (docker-compose) > .env file (local dev) > defaults
def _load_env_file():
    """Load .env file from multiple possible locations with error handling."""
    # Possible .env locations (in priority order)
    current_file = Path(__file__).resolve()
    possible_paths = [
        # Docker environment: /app/.env (same level as backend/)
        current_file.parent.parent.parent / '.env',
        # Local development: project_root/.env
        current_file.parent.parent.parent.parent / '.env',
        # Fallback: current working directory
        Path.cwd() / '.env',
    ]

    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)  # Don't override existing env vars
            logger.info(f"Loaded .env from: {env_path}")
            return True

    logger.warning("No .env file found - using environment variables and defaults")
    return False

_load_env_file()


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

    @classmethod
    def from_env(cls, prefix: str, name: str) -> "AIProviderConfig":
        """Create config from environment variables with given prefix."""
        return cls(
            name=name,
            api_key=os.getenv(f"{prefix}_API_KEY", ""),
            base_url=os.getenv(f"{prefix}_BASE_URL") or None,
            model=os.getenv(f"{prefix}_MODEL", "gpt-4o-mini"),
            max_retries=int(os.getenv(f"{prefix}_MAX_RETRIES", "2")),
            temperature=float(os.getenv(f"{prefix}_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv(f"{prefix}_MAX_TOKENS", "500")),
        )

    def is_valid(self) -> bool:
        """Check if this provider has valid configuration."""
        return bool(self.api_key)


@dataclass
class AIPlayerConfig:
    """Configuration for AI player to provider mapping."""
    seat_id: int
    provider_name: str  # References AIProviderConfig.name


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        # Default OpenAI configuration (backward compatible)
        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        self.OPENAI_BASE_URL: Optional[str] = os.getenv("OPENAI_BASE_URL") or None

        # Default LLM settings
        self.LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))
        self.LLM_USE_MOCK: bool = os.getenv("LLM_USE_MOCK", "false").lower() == "true"

        # Application settings
        self.DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        self.DATA_DIR: str = os.getenv("DATA_DIR", "data")  # 数据存储目录（用于SQLite等）

        # Security settings
        self.DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
        self.ADMIN_KEY: str = os.getenv("ADMIN_KEY", "")
        # P1-SEC-002: Control X-Admin-Key availability (default disabled in production)
        self.ADMIN_KEY_ENABLED: bool = os.getenv("ADMIN_KEY_ENABLED", "false").lower() == "true"

        # T-SEC-005: CORS configuration
        # CORS_ORIGINS: comma-separated list of allowed origins, or "*" for all
        # Example: "http://localhost:3000,https://example.com"
        # If "*", credentials will be disabled (per CORS spec)
        #
        # SECURITY WARNING: In production, NEVER use "*" with cookie-based authentication.
        # Always specify exact origins to prevent CSRF attacks.
        cors_origins_str = os.getenv("CORS_ORIGINS", "*")
        if cors_origins_str == "*":
            self.CORS_ORIGINS: list[str] = ["*"]
            self.CORS_ALLOW_CREDENTIALS: bool = False  # Cannot use credentials with wildcard
            # Log warning if running in production mode
            if not os.getenv("DEBUG", "false").lower() == "true":
                import logging
                logging.warning(
                    "SECURITY WARNING: CORS_ORIGINS='*' in production mode. "
                    "This is insecure with cookie-based authentication. "
                    "Set specific origins (e.g., CORS_ORIGINS='https://example.com')"
                )
        else:
            self.CORS_ORIGINS = [o.strip() for o in cors_origins_str.split(",") if o.strip()]
            self.CORS_ALLOW_CREDENTIALS = True

        # JWT Authentication settings
        self.JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
        self.JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))  # 7 days

        # OAuth2 Configuration - linux.do
        self.LINUXDO_CLIENT_ID: str = os.getenv("LINUXDO_CLIENT_ID", "")
        self.LINUXDO_CLIENT_SECRET: str = os.getenv("LINUXDO_CLIENT_SECRET", "")
        self.LINUXDO_AUTHORIZE_URL: str = os.getenv("LINUXDO_AUTHORIZE_URL", "https://linux.do/oauth2/authorize")
        self.LINUXDO_TOKEN_URL: str = os.getenv("LINUXDO_TOKEN_URL", "https://linux.do/oauth2/token")
        self.LINUXDO_USERINFO_URL: str = os.getenv("LINUXDO_USERINFO_URL", "https://linux.do/oauth2/userinfo")
        self.LINUXDO_REDIRECT_URI: str = os.getenv("LINUXDO_REDIRECT_URI", "")
        self.LINUXDO_SCOPES: str = os.getenv("LINUXDO_SCOPES", "openid email profile")

        # AI Analysis configuration (independent from game AI)
        self.ANALYSIS_PROVIDER: Optional[str] = os.getenv("ANALYSIS_PROVIDER") or None
        self.ANALYSIS_MODEL: str = os.getenv("ANALYSIS_MODEL", self.LLM_MODEL)
        self.ANALYSIS_MAX_TOKENS: int = int(os.getenv("ANALYSIS_MAX_TOKENS", "4000"))
        self.ANALYSIS_TEMPERATURE: float = float(os.getenv("ANALYSIS_TEMPERATURE", "0.7"))
        self.ANALYSIS_MODE: str = os.getenv("ANALYSIS_MODE", "comprehensive")  # comprehensive/quick/custom
        self.ANALYSIS_LANGUAGE: str = os.getenv("ANALYSIS_LANGUAGE", "auto")  # auto/zh/en
        self.ANALYSIS_CACHE_ENABLED: bool = os.getenv("ANALYSIS_CACHE_ENABLED", "true").lower() == "true"

        # Multi-provider configuration
        self._providers: dict[str, AIProviderConfig] = {}
        self._player_mappings: dict[int, str] = {}  # seat_id -> provider_name

        self._load_providers()
        self._load_player_mappings()
        self._log_configuration_summary()

    def _load_providers(self):
        """Load AI provider configurations from environment.

        This method only loads provider definitions, does not establish player mappings.
        Player mappings are handled separately in _load_player_mappings().
        """
        # Default provider (OpenAI)
        default_provider = AIProviderConfig(
            name="default",
            api_key=self.OPENAI_API_KEY,
            base_url=self.OPENAI_BASE_URL,
            model=self.LLM_MODEL,
            max_retries=self.LLM_MAX_RETRIES,
        )
        if default_provider.is_valid():
            self._providers["default"] = default_provider

        # Load named providers: OPENAI_*, ANTHROPIC_*, DEEPSEEK_*, etc.
        named_providers = ["OPENAI", "ANTHROPIC", "DEEPSEEK", "MOONSHOT", "QWEN", "GLM", "DOUBAO", "MINIMAX"]
        for provider_name in named_providers:
            api_key = os.getenv(f"{provider_name}_API_KEY")
            if api_key:
                provider = AIProviderConfig(
                    name=provider_name.lower(),
                    api_key=api_key,
                    base_url=os.getenv(f"{provider_name}_BASE_URL") or None,
                    model=os.getenv(f"{provider_name}_MODEL", self._get_default_model(provider_name)),
                    max_retries=int(os.getenv(f"{provider_name}_MAX_RETRIES", "2")),
                    temperature=float(os.getenv(f"{provider_name}_TEMPERATURE", "0.7")),
                    max_tokens=int(os.getenv(f"{provider_name}_MAX_TOKENS", "500")),
                )
                self._providers[provider_name.lower()] = provider

        # Load additional custom providers from AI_PROVIDER_* env vars
        # Format: AI_PROVIDER_1_NAME, AI_PROVIDER_1_API_KEY, etc.
        for i in range(1, 10):  # Support up to 9 custom providers
            prefix = f"AI_PROVIDER_{i}"
            name = os.getenv(f"{prefix}_NAME")
            if name:
                provider = AIProviderConfig.from_env(prefix, name)
                if provider.is_valid():
                    self._providers[name] = provider

        # Load per-player specific providers (座位 2-9)
        # Format: AI_PLAYER_2_API_KEY, AI_PLAYER_2_MODEL, etc.
        # These create dedicated providers named "player_{seat_id}"
        # Note: Mapping is NOT established here, only provider definition is created
        for seat_id in range(2, 10):
            prefix = f"AI_PLAYER_{seat_id}"
            api_key = os.getenv(f"{prefix}_API_KEY")

            # Only create player-specific provider if API_KEY is explicitly configured
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
                )
                if provider.is_valid():
                    self._providers[provider_name] = provider

    def _get_default_model(self, provider_name: str) -> str:
        """Get default model for a provider."""
        defaults = {
            "OPENAI": "gpt-4o-mini",
            "ANTHROPIC": "claude-3-haiku-20240307",
            "DEEPSEEK": "deepseek-chat",
            "MOONSHOT": "moonshot-v1-8k",
            "QWEN": "qwen-turbo",
            "GLM": "glm-4-flash",
            "DOUBAO": "doubao-pro-4k",
            "MINIMAX": "abab6.5s-chat",
        }
        return defaults.get(provider_name, "gpt-4o-mini")

    def _load_player_mappings(self):
        """Load AI player to provider mappings with correct priority.

        Priority order (low to high, later overrides earlier):
        1. Auto-mapping for player-specific configs (player_{seat_id})
        2. JSON batch mapping (AI_PLAYER_MAPPING)
        3. Individual mapping (AI_PLAYER_{seat}_PROVIDER) - highest priority

        This ensures that explicit provider mappings always take precedence.
        """
        # Priority 1 (Lowest): Auto-map players with specific provider configs
        # If player_{seat_id} provider exists, automatically map to it
        for seat_id in range(2, 10):
            provider_name = f"player_{seat_id}"
            if provider_name in self._providers:
                self._player_mappings[seat_id] = provider_name

        # Priority 2 (Medium): JSON batch mapping
        # Format: AI_PLAYER_MAPPING={"2":"openai","3":"anthropic",...}
        mapping_json = os.getenv("AI_PLAYER_MAPPING")
        if mapping_json:
            try:
                mapping = json.loads(mapping_json)
                for seat_str, provider in mapping.items():
                    seat_id = int(seat_str)
                    if provider in self._providers:
                        self._player_mappings[seat_id] = provider
                    else:
                        logger.warning(
                            f"AI_PLAYER_MAPPING: provider '{provider}' not found for seat {seat_id}"
                        )
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse AI_PLAYER_MAPPING: {e}")

        # Priority 3 (Highest): Individual mapping per seat
        # Format: AI_PLAYER_{seat}_PROVIDER=openai
        # This overrides both auto-mapping and JSON mapping
        for seat_id in range(1, 10):
            provider = os.getenv(f"AI_PLAYER_{seat_id}_PROVIDER")
            if provider:
                if provider in self._providers:
                    self._player_mappings[seat_id] = provider
                else:
                    # P2-2 Fix: Use module-level logger instead of re-importing
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

    def get_analysis_provider(self) -> Optional[AIProviderConfig]:
        """Get provider configuration for game analysis (prioritized).

        Priority:
        1. Dedicated ANALYSIS_PROVIDER if specified
        2. Default provider with analysis settings
        3. None (will use fallback mode)
        """
        # Priority 1: Dedicated ANALYSIS_PROVIDER
        if self.ANALYSIS_PROVIDER:
            provider = self._providers.get(self.ANALYSIS_PROVIDER.lower())
            if provider and provider.is_valid():
                # Override with analysis-specific settings
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
        default = self._providers.get("default")
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

        return None

    def validate_analysis_config(self) -> tuple[bool, list[str]]:
        """Validate analysis configuration.

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Check if any provider is available
        if not self._providers:
            errors.append("No AI provider configured. Set OPENAI_API_KEY or other provider.")

        # Check analysis provider if specified
        if self.ANALYSIS_PROVIDER:
            provider_key = self.ANALYSIS_PROVIDER.lower()
            if provider_key not in self._providers:
                errors.append(f"ANALYSIS_PROVIDER '{self.ANALYSIS_PROVIDER}' not found in configured providers.")
            elif not self._providers[provider_key].is_valid():
                errors.append(f"ANALYSIS_PROVIDER '{self.ANALYSIS_PROVIDER}' has invalid configuration.")

        # Check analysis mode
        valid_modes = ["comprehensive", "quick", "custom"]
        if self.ANALYSIS_MODE not in valid_modes:
            errors.append(f"ANALYSIS_MODE must be one of {valid_modes}, got '{self.ANALYSIS_MODE}'")

        # Check analysis language
        valid_languages = ["auto", "zh", "en"]
        if self.ANALYSIS_LANGUAGE not in valid_languages:
            errors.append(f"ANALYSIS_LANGUAGE must be one of {valid_languages}, got '{self.ANALYSIS_LANGUAGE}'")

        return (len(errors) == 0, errors)

    def _log_configuration_summary(self):
        """Log configuration summary for debugging."""
        logger.info(f"AI Configuration loaded: {len(self._providers)} providers configured")

        # Log all providers
        for name, provider in self._providers.items():
            logger.info(
                f"  Provider '{name}': model={provider.model}, "
                f"base_url={provider.base_url or 'default'}"
            )

        # Log player mappings
        if self._player_mappings:
            logger.info("Player to provider mappings:")
            for seat_id in sorted(self._player_mappings.keys()):
                provider_name = self._player_mappings[seat_id]
                provider = self._providers.get(provider_name)
                model_info = f" (model: {provider.model})" if provider else ""
                logger.info(f"  Seat {seat_id} -> {provider_name}{model_info}")
        else:
            logger.info("No explicit player mappings - all players use default provider")

        # Log analysis configuration
        logger.info("=" * 50)
        logger.info("Analysis Configuration:")
        logger.info(f"  Mode: {self.ANALYSIS_MODE}")
        logger.info(f"  Language: {self.ANALYSIS_LANGUAGE}")
        logger.info(f"  Model: {self.ANALYSIS_MODEL}")
        logger.info(f"  Max Tokens: {self.ANALYSIS_MAX_TOKENS}")
        logger.info(f"  Cache Enabled: {self.ANALYSIS_CACHE_ENABLED}")

        analysis_provider = self.get_analysis_provider()
        if analysis_provider:
            logger.info(f"  Provider: {analysis_provider.name} (model: {analysis_provider.model})")
        else:
            logger.warning("  Provider: None - Analysis will use fallback mode")

        is_valid, errors = self.validate_analysis_config()
        if not is_valid:
            logger.warning("Analysis configuration issues:")
            for error in errors:
                logger.warning(f"  - {error}")


settings = Settings()
