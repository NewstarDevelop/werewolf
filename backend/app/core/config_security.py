"""Security configuration validation.

Extracted from config.py for better maintainability.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SecurityConfig:
    """Security-related configuration settings."""

    def __init__(self):
        # Debug mode
        self.DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
        self.DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"

        # Admin panel
        self.ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

        # Trusted proxies for X-Forwarded-For
        trusted_proxies_str = os.getenv("TRUSTED_PROXIES", "")
        self.TRUSTED_PROXIES: list[str] = [
            p.strip() for p in trusted_proxies_str.split(",") if p.strip()
        ]
        self.MAX_PROXY_HOPS: int = int(os.getenv("MAX_PROXY_HOPS", "5"))

        # CORS configuration
        cors_origins_str = os.getenv("CORS_ORIGINS", "*")
        # MINOR FIX: Make CORS credentials configurable
        cors_credentials_str = os.getenv("CORS_ALLOW_CREDENTIALS", "auto")

        if cors_origins_str == "*":
            self.CORS_ORIGINS: list[str] = ["*"]
            # Credentials must be False when origins is "*"
            self.CORS_ALLOW_CREDENTIALS: bool = False
            if not self.DEBUG:
                logger.warning(
                    "SECURITY WARNING: CORS_ORIGINS='*' in production mode. "
                    "This is insecure with cookie-based authentication."
                )
        else:
            self.CORS_ORIGINS = [o.strip() for o in cors_origins_str.split(",") if o.strip()]
            # Auto mode: enable credentials for specific origins (default behavior)
            # Can be explicitly disabled with CORS_ALLOW_CREDENTIALS=false
            if cors_credentials_str.lower() == "auto":
                self.CORS_ALLOW_CREDENTIALS = True
            else:
                self.CORS_ALLOW_CREDENTIALS = cors_credentials_str.lower() == "true"

        # JWT settings
        self.JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
        self.JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))

        # Frontend URL for CORS and WebSocket
        self.FRONTEND_URL: Optional[str] = os.getenv("FRONTEND_URL") or None

        # WebSocket origins
        ws_origins_str = os.getenv("ALLOWED_WS_ORIGINS", "")
        if ws_origins_str:
            self.ALLOWED_WS_ORIGINS: list[str] = [o.strip() for o in ws_origins_str.split(",") if o.strip()]
        elif self.FRONTEND_URL:
            self.ALLOWED_WS_ORIGINS = [self.FRONTEND_URL]
        else:
            self.ALLOWED_WS_ORIGINS = []

    def validate(self) -> tuple[list[str], list[str]]:
        """Validate security-critical configuration.

        Returns:
            Tuple of (warnings, errors) lists
        """
        warnings = []
        errors = []

        if self.DEBUG:
            return warnings, errors

        # Check CORS_ORIGINS
        if self.CORS_ORIGINS == ["*"]:
            errors.append(
                "CORS_ORIGINS='*' is not allowed in production. "
                "Set specific origins (e.g., CORS_ORIGINS='https://example.com')"
            )

        # Check JWT_SECRET_KEY
        if not self.JWT_SECRET_KEY or len(self.JWT_SECRET_KEY) < 32:
            errors.append(
                "JWT_SECRET_KEY must be at least 32 characters in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )

        # Check FRONTEND_URL
        if not self.FRONTEND_URL and not self.ALLOWED_WS_ORIGINS:
            warnings.append(
                "FRONTEND_URL or ALLOWED_WS_ORIGINS not set. "
                "WebSocket origin validation may not work correctly."
            )

        for warning in warnings:
            logger.warning(f"SECURITY CONFIG: {warning}")
        for error in errors:
            logger.error(f"SECURITY CONFIG ERROR: {error}")

        return warnings, errors


class OAuthConfig:
    """OAuth2 configuration for linux.do."""

    def __init__(self):
        self.LINUXDO_CLIENT_ID: str = os.getenv("LINUXDO_CLIENT_ID", "")
        self.LINUXDO_CLIENT_SECRET: str = os.getenv("LINUXDO_CLIENT_SECRET", "")
        self.LINUXDO_AUTHORIZE_URL: str = os.getenv("LINUXDO_AUTHORIZE_URL", "https://connect.linux.do/oauth2/authorize")
        self.LINUXDO_TOKEN_URL: str = os.getenv("LINUXDO_TOKEN_URL", "https://connect.linux.do/oauth2/token")
        self.LINUXDO_USERINFO_URL: str = os.getenv("LINUXDO_USERINFO_URL", "https://connect.linux.do/api/user")
        self.LINUXDO_REDIRECT_URI: str = os.getenv("LINUXDO_REDIRECT_URI", "")
        self.LINUXDO_SCOPES: str = os.getenv("LINUXDO_SCOPES", "user")

    def is_configured(self) -> bool:
        """Check if OAuth is properly configured."""
        return bool(self.LINUXDO_CLIENT_ID and self.LINUXDO_CLIENT_SECRET)
