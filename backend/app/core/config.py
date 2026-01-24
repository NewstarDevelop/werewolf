"""Application configuration with multi-AI provider support.

Refactored: Provider, security, and analysis configs extracted to separate modules.
"""
import os
import logging
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

from .config_providers import AIProviderConfig, AIPlayerConfig, ProviderManager
from .config_security import SecurityConfig, OAuthConfig
from .config_analysis import AnalysisConfig

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = ["settings", "AIProviderConfig", "AIPlayerConfig", "ENV_FILE_PATH", "ENV_FILE_LOADED"]

# Resolved .env path used at startup
ENV_FILE_PATH: Optional[Path] = None
ENV_FILE_LOADED: bool = False


def _load_env_file():
    """Load .env file from multiple possible locations with error handling."""
    global ENV_FILE_PATH, ENV_FILE_LOADED
    current_file = Path(__file__).resolve()
    possible_paths = [
        current_file.parent.parent.parent / '.env',
        current_file.parent.parent.parent.parent / '.env',
        Path.cwd() / '.env',
    ]

    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            ENV_FILE_PATH = env_path
            ENV_FILE_LOADED = True
            logger.info(f"Loaded .env from: {env_path}")
            return True

    logger.warning("No .env file found - using environment variables and defaults")
    return False


_load_env_file()


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
        self.DATA_DIR: str = os.getenv("DATA_DIR", "/app/data" if os.path.exists("/app") else "data")

        # Database configuration
        default_db_url = f"sqlite:///{self.DATA_DIR}/werewolf.db"
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", default_db_url)
        self.DATABASE_URL_ASYNC: str = self._derive_async_database_url(self.DATABASE_URL)

        # Admin runtime config management
        self.ENV_MANAGEMENT_ENABLED: bool = os.getenv("ENV_MANAGEMENT_ENABLED", "false").lower() == "true"

        # Update Agent configuration
        self.UPDATE_AGENT_ENABLED: bool = os.getenv("UPDATE_AGENT_ENABLED", "false").lower() == "true"
        self.UPDATE_AGENT_URL: str = os.getenv("UPDATE_AGENT_URL", "")
        self.UPDATE_AGENT_TOKEN: str = os.getenv("UPDATE_AGENT_TOKEN", "")
        self.UPDATE_AGENT_TIMEOUT_SECONDS: float = float(os.getenv("UPDATE_AGENT_TIMEOUT_SECONDS", "3.0"))
        self.UPDATE_BLOCK_IF_PLAYING_ROOMS: bool = os.getenv("UPDATE_BLOCK_IF_PLAYING_ROOMS", "true").lower() == "true"
        self.UPDATE_BLOCK_IF_ACTIVE_GAME_WS: bool = os.getenv("UPDATE_BLOCK_IF_ACTIVE_GAME_WS", "true").lower() == "true"
        self.UPDATE_FORCE_CONFIRM_PHRASE: str = os.getenv("UPDATE_FORCE_CONFIRM_PHRASE", "UPDATE")

        # Initialize security config
        self._security = SecurityConfig()
        self._oauth = OAuthConfig()

        # Copy security settings to top level for backward compatibility
        self.DEBUG_MODE = self._security.DEBUG_MODE
        self.ADMIN_PASSWORD = self._security.ADMIN_PASSWORD
        self.TRUSTED_PROXIES = self._security.TRUSTED_PROXIES
        self.MAX_PROXY_HOPS = self._security.MAX_PROXY_HOPS
        self.CORS_ORIGINS = self._security.CORS_ORIGINS
        self.CORS_ALLOW_CREDENTIALS = self._security.CORS_ALLOW_CREDENTIALS
        self.JWT_SECRET_KEY = self._security.JWT_SECRET_KEY
        self.JWT_ALGORITHM = self._security.JWT_ALGORITHM
        self.JWT_EXPIRE_MINUTES = self._security.JWT_EXPIRE_MINUTES
        self.FRONTEND_URL = self._security.FRONTEND_URL
        self.ALLOWED_WS_ORIGINS = self._security.ALLOWED_WS_ORIGINS

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

        # Initialize analysis config
        self._analysis = AnalysisConfig(self.LLM_MODEL)

        # Copy analysis settings for backward compatibility
        self.ANALYSIS_PROVIDER = self._analysis.ANALYSIS_PROVIDER
        self.ANALYSIS_MODEL = self._analysis.ANALYSIS_MODEL
        self.ANALYSIS_MAX_TOKENS = self._analysis.ANALYSIS_MAX_TOKENS
        self.ANALYSIS_TEMPERATURE = self._analysis.ANALYSIS_TEMPERATURE
        self.ANALYSIS_MODE = self._analysis.ANALYSIS_MODE
        self.ANALYSIS_LANGUAGE = self._analysis.ANALYSIS_LANGUAGE
        self.ANALYSIS_CACHE_ENABLED = self._analysis.ANALYSIS_CACHE_ENABLED

        # Log configuration summary
        self._log_configuration_summary()
        self._validate_security_config()

    def _derive_async_database_url(self, url: str) -> str:
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

    def _validate_security_config(self) -> tuple[list[str], list[str]]:
        """Validate security-critical configuration at startup."""
        return self._security.validate()

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
