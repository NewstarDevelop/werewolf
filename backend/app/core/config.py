"""Application configuration with multi-AI provider support.

Refactored to use Pydantic BaseSettings for declarative environment variable binding.
Provider, security, and analysis configs extracted to separate modules.
"""
import os
import logging
from typing import Any, Optional
from pathlib import Path
from dotenv import load_dotenv

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .config_providers import AIProviderConfig, AIPlayerConfig, ProviderManager
from .config_security import SecurityConfig, OAuthConfig
from .config_analysis import AnalysisConfig

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = ["settings", "AIProviderConfig", "AIPlayerConfig", "ENV_FILE_PATH", "ENV_FILE_LOADED"]

# Resolved .env path used at startup
ENV_FILE_PATH: Optional[Path] = None
ENV_FILE_LOADED: bool = False


def _find_env_file() -> Optional[Path]:
    """Find .env file from multiple possible locations."""
    global ENV_FILE_PATH, ENV_FILE_LOADED
    current_file = Path(__file__).resolve()
    possible_paths = [
        current_file.parent.parent.parent / '.env',
        current_file.parent.parent.parent.parent / '.env',
        Path.cwd() / '.env',
    ]

    for env_path in possible_paths:
        if env_path.exists():
            ENV_FILE_PATH = env_path
            ENV_FILE_LOADED = True
            logger.info(f"Found .env at: {env_path}")
            return env_path

    logger.warning("No .env file found - using environment variables and defaults")
    return None


# Pre-load .env so that all BaseSettings subclasses can read from it.
# This is also needed for ProviderManager which still uses os.getenv().
_env_path = _find_env_file()
if _env_path:
    load_dotenv(dotenv_path=_env_path, override=False)


def _derive_async_database_url(url: str) -> str:
    """Derive async database URL from sync URL."""
    if "+aiosqlite" in url or "+asyncpg" in url:
        return url
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://")
    return url


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Uses Pydantic BaseSettings for automatic env var binding and type validation.
    Sub-configurations (security, OAuth, analysis) are composed via model_validator.
    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Default OpenAI configuration ---
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: Optional[str] = None

    # --- Default LLM settings ---
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_RETRIES: int = 2
    LLM_USE_MOCK: bool = False

    # --- Application settings ---
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    DATA_DIR: str = "/app/data" if os.path.exists("/app") else "data"

    # --- Database configuration ---
    DATABASE_URL: Optional[str] = None  # Computed in validator if not set

    # --- Admin runtime config management ---
    ENV_MANAGEMENT_ENABLED: bool = False

    # --- Update Agent configuration ---
    UPDATE_AGENT_ENABLED: bool = False
    UPDATE_AGENT_URL: str = ""
    UPDATE_AGENT_TOKEN: str = ""
    UPDATE_AGENT_TIMEOUT_SECONDS: float = 3.0
    UPDATE_BLOCK_IF_PLAYING_ROOMS: bool = True
    UPDATE_BLOCK_IF_ACTIVE_GAME_WS: bool = True
    UPDATE_FORCE_CONFIRM_PHRASE: str = "UPDATE"

    # --- Composed sub-config objects (initialized in validator) ---
    _security: SecurityConfig = SecurityConfig()
    _oauth: OAuthConfig = OAuthConfig()
    _analysis: AnalysisConfig = AnalysisConfig()
    _provider_manager: ProviderManager = ProviderManager()

    # --- Computed fields (set by model_validator) ---
    DATABASE_URL_ASYNC: str = ""

    # --- Backward-compatible security attributes ---
    DEBUG_MODE: bool = False
    ADMIN_PASSWORD: str = ""
    TRUSTED_PROXIES: Any = ""  # str from env, overwritten to list[str] by validator
    MAX_PROXY_HOPS: int = 5
    CORS_ORIGINS: Any = "*"  # str from env, overwritten to list[str] by validator
    CORS_ALLOW_CREDENTIALS: bool = False
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7
    FRONTEND_URL: Optional[str] = None
    ALLOWED_WS_ORIGINS: Any = ""  # str from env, overwritten to list[str] by validator

    # --- Token encryption ---
    TOKEN_ENCRYPTION_KEY: str = ""

    # --- Backward-compatible OAuth attributes ---
    LINUXDO_CLIENT_ID: str = ""
    LINUXDO_CLIENT_SECRET: str = ""
    LINUXDO_AUTHORIZE_URL: str = "https://connect.linux.do/oauth2/authorize"
    LINUXDO_TOKEN_URL: str = "https://connect.linux.do/oauth2/token"
    LINUXDO_USERINFO_URL: str = "https://connect.linux.do/api/user"
    LINUXDO_REDIRECT_URI: str = ""
    LINUXDO_SCOPES: str = "user"

    # --- Backward-compatible analysis attributes ---
    ANALYSIS_PROVIDER: Optional[str] = None
    ANALYSIS_MODEL: str = "gpt-4o-mini"
    ANALYSIS_MAX_TOKENS: int = 4000
    ANALYSIS_TEMPERATURE: float = 0.7
    ANALYSIS_MODE: str = "comprehensive"
    ANALYSIS_LANGUAGE: str = "auto"
    ANALYSIS_CACHE_ENABLED: bool = True

    @model_validator(mode="after")
    def _initialize_composed_configs(self) -> "Settings":
        """Initialize sub-configurations and copy their values for backward compatibility."""
        # Database URL defaults
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite:///{self.DATA_DIR}/werewolf.db"
        self.DATABASE_URL_ASYNC = _derive_async_database_url(self.DATABASE_URL)

        # Initialize sub-configs
        self._security = SecurityConfig()
        self._oauth = OAuthConfig()
        self._analysis = AnalysisConfig()

        # Copy security settings to top level
        self.DEBUG_MODE = self._security.DEBUG_MODE
        self.ADMIN_PASSWORD = self._security.ADMIN_PASSWORD
        self.TRUSTED_PROXIES = self._security._trusted_proxies_list
        self.MAX_PROXY_HOPS = self._security.MAX_PROXY_HOPS
        self.CORS_ORIGINS = self._security._cors_origins_list
        self.CORS_ALLOW_CREDENTIALS = self._security._cors_allow_credentials_bool
        self.JWT_SECRET_KEY = self._security.JWT_SECRET_KEY
        self.JWT_ALGORITHM = self._security.JWT_ALGORITHM
        self.JWT_EXPIRE_MINUTES = self._security.JWT_EXPIRE_MINUTES
        self.FRONTEND_URL = self._security.FRONTEND_URL
        self.ALLOWED_WS_ORIGINS = self._security._allowed_ws_origins_list

        # Copy OAuth settings
        self.LINUXDO_CLIENT_ID = self._oauth.LINUXDO_CLIENT_ID
        self.LINUXDO_CLIENT_SECRET = self._oauth.LINUXDO_CLIENT_SECRET
        self.LINUXDO_AUTHORIZE_URL = self._oauth.LINUXDO_AUTHORIZE_URL
        self.LINUXDO_TOKEN_URL = self._oauth.LINUXDO_TOKEN_URL
        self.LINUXDO_USERINFO_URL = self._oauth.LINUXDO_USERINFO_URL
        self.LINUXDO_REDIRECT_URI = self._oauth.LINUXDO_REDIRECT_URI
        self.LINUXDO_SCOPES = self._oauth.LINUXDO_SCOPES

        # Initialize provider manager
        self._provider_manager = ProviderManager()
        self._provider_manager.load_providers(
            self.OPENAI_API_KEY,
            self.OPENAI_BASE_URL,
            self.LLM_MODEL,
            self.LLM_MAX_RETRIES
        )
        self._provider_manager.load_player_mappings()

        # Copy analysis settings
        self.ANALYSIS_PROVIDER = self._analysis.ANALYSIS_PROVIDER
        self.ANALYSIS_MODEL = self._analysis.ANALYSIS_MODEL or self.LLM_MODEL
        self.ANALYSIS_MAX_TOKENS = self._analysis.ANALYSIS_MAX_TOKENS
        self.ANALYSIS_TEMPERATURE = self._analysis.ANALYSIS_TEMPERATURE
        self.ANALYSIS_MODE = self._analysis.ANALYSIS_MODE
        self.ANALYSIS_LANGUAGE = self._analysis.ANALYSIS_LANGUAGE
        self.ANALYSIS_CACHE_ENABLED = self._analysis.ANALYSIS_CACHE_ENABLED

        # Log configuration summary
        self._log_configuration_summary()
        # NOTE: Security validation is performed in main.py _startup() where
        # warnings/errors are properly collected and acted upon (fail-fast).
        # Do NOT call _validate_security_config() here — the result would be
        # discarded and the validation would run twice.

        return self

    def _validate_security_config(self) -> tuple[list[str], list[str]]:
        """Validate security-critical configuration at startup."""
        return self._security.validate_security()

    # Provider management methods (delegate to ProviderManager)
    @property
    def _providers(self) -> dict[str, AIProviderConfig]:
        """MINOR FIX: Return a copy to prevent external modification of internal state."""
        return self._provider_manager._providers.copy()

    @property
    def _player_mappings(self) -> dict[int, str]:
        """MINOR FIX: Return a copy to prevent external modification of internal state."""
        return self._provider_manager._player_mappings.copy()

    def get_provider(self, name: str) -> Optional[AIProviderConfig]:
        """Get provider configuration by name."""
        return self._provider_manager.get_provider(name)

    def get_provider_for_player(self, seat_id: int) -> Optional[AIProviderConfig]:
        """Get provider configuration for a specific player seat."""
        return self._provider_manager.get_provider_for_player(seat_id)

    def get_all_providers(self) -> dict[str, AIProviderConfig]:
        """Get all configured providers."""
        return self._provider_manager.get_all_providers()

    def get_player_mappings(self) -> dict[int, str]:
        """Get all player to provider mappings."""
        return self._provider_manager.get_player_mappings()

    # Analysis methods (delegate to AnalysisConfig)
    def get_analysis_provider(self) -> Optional[AIProviderConfig]:
        """Get provider configuration for game analysis."""
        return self._analysis.get_provider(self._provider_manager.get_all_providers())

    def validate_analysis_config(self) -> tuple[bool, list[str]]:
        """Validate analysis configuration."""
        return self._analysis.validate(self._provider_manager.get_all_providers())

    def _log_configuration_summary(self):
        """Log configuration summary for debugging."""
        self._provider_manager.log_summary()
        self._analysis.log_summary(self._provider_manager.get_all_providers())


settings = Settings()
