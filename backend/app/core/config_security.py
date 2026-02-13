"""Security configuration validation.

Extracted from config.py for better maintainability.
Refactored to use Pydantic BaseSettings for declarative environment variable binding.
"""
import logging
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _parse_comma_list(value: str) -> list[str]:
    """Parse a comma-separated string into a list of stripped, non-empty strings."""
    return [item.strip() for item in value.split(",") if item.strip()]


class SecurityConfig(BaseSettings):
    """Security-related configuration settings."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Debug mode
    DEBUG: bool = False
    DEBUG_MODE: bool = False

    # Admin panel
    ADMIN_PASSWORD: str = ""

    # Trusted proxies for X-Forwarded-For (raw comma-separated string)
    TRUSTED_PROXIES: str = ""
    MAX_PROXY_HOPS: int = 5

    # CORS configuration (raw comma-separated string)
    CORS_ORIGINS: str = "*"
    CORS_ALLOW_CREDENTIALS: str = "auto"

    # JWT settings
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week

    # Frontend URL for CORS and WebSocket
    FRONTEND_URL: Optional[str] = None

    # WebSocket origins (raw comma-separated string)
    ALLOWED_WS_ORIGINS: str = ""

    # --- Computed fields (set by model_validator) ---
    _cors_origins_list: list[str] = []
    _cors_allow_credentials_bool: bool = False
    _trusted_proxies_list: list[str] = []
    _allowed_ws_origins_list: list[str] = []

    @model_validator(mode="after")
    def _resolve_computed_fields(self) -> "SecurityConfig":
        """Resolve comma-separated strings and conditional logic after field loading."""
        # Trusted proxies
        self._trusted_proxies_list = _parse_comma_list(self.TRUSTED_PROXIES)

        # CORS origins
        if self.CORS_ORIGINS.strip() == "*":
            self._cors_origins_list = ["*"]
            self._cors_allow_credentials_bool = False
            if not self.DEBUG:
                logger.warning(
                    "SECURITY WARNING: CORS_ORIGINS='*' in production mode. "
                    "This is insecure with cookie-based authentication."
                )
        else:
            self._cors_origins_list = _parse_comma_list(self.CORS_ORIGINS)
            if self.CORS_ALLOW_CREDENTIALS.lower() == "auto":
                self._cors_allow_credentials_bool = True
            else:
                self._cors_allow_credentials_bool = self.CORS_ALLOW_CREDENTIALS.lower() == "true"

        # WebSocket origins
        if self.ALLOWED_WS_ORIGINS:
            self._allowed_ws_origins_list = _parse_comma_list(self.ALLOWED_WS_ORIGINS)
        elif self.FRONTEND_URL:
            self._allowed_ws_origins_list = [self.FRONTEND_URL]
        else:
            self._allowed_ws_origins_list = []

        return self

    def validate_security(self) -> tuple[list[str], list[str]]:
        """Validate security-critical configuration.

        Returns:
            Tuple of (warnings, errors) lists
        """
        warnings: list[str] = []
        errors: list[str] = []

        if self.DEBUG:
            return warnings, errors

        # Check CORS_ORIGINS
        if self._cors_origins_list == ["*"]:
            errors.append(
                "CORS_ORIGINS='*' is not allowed in production. "
                "Set specific origins (e.g., CORS_ORIGINS='https://example.com')"
            )

        # Check JWT_SECRET_KEY
        if not self.JWT_SECRET_KEY or len(self.JWT_SECRET_KEY) < 32:
            errors.append(
                "JWT_SECRET_KEY must be at least 32 characters in production. "
                'Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )

        # Check FRONTEND_URL
        if not self.FRONTEND_URL and not self._allowed_ws_origins_list:
            warnings.append(
                "FRONTEND_URL or ALLOWED_WS_ORIGINS not set. "
                "WebSocket origin validation may not work correctly."
            )

        for warning in warnings:
            logger.warning(f"SECURITY CONFIG: {warning}")
        for error in errors:
            logger.error(f"SECURITY CONFIG ERROR: {error}")

        return warnings, errors


class OAuthConfig(BaseSettings):
    """OAuth2 configuration for linux.do."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    LINUXDO_CLIENT_ID: str = ""
    LINUXDO_CLIENT_SECRET: str = ""
    LINUXDO_AUTHORIZE_URL: str = "https://connect.linux.do/oauth2/authorize"
    LINUXDO_TOKEN_URL: str = "https://connect.linux.do/oauth2/token"
    LINUXDO_USERINFO_URL: str = "https://connect.linux.do/api/user"
    LINUXDO_REDIRECT_URI: str = ""
    LINUXDO_SCOPES: str = "user"

    def is_configured(self) -> bool:
        """Check if OAuth is properly configured."""
        return bool(self.LINUXDO_CLIENT_ID and self.LINUXDO_CLIENT_SECRET)
