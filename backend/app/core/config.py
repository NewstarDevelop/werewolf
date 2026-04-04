from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Core
    APP_NAME: str = "Werewolf"
    DEBUG: bool = False
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    DATABASE_URL: str = "sqlite+aiosqlite:///./werewolf.db"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Auth
    ADMIN_PASSWORD: str = ""

    # OAuth - linux.do
    OAUTH_LINUXDO_CLIENT_ID: str = ""
    OAUTH_LINUXDO_CLIENT_SECRET: str = ""
    OAUTH_LINUXDO_REDIRECT_URI: str = ""

    # LLM Default
    LLM_DEFAULT_PROVIDER: str = "mock"
    LLM_DEFAULT_API_KEY: str = ""
    LLM_DEFAULT_MODEL: str = ""
    LLM_DEFAULT_BASE_URL: str = ""
    LLM_DEFAULT_TEMPERATURE: float = 0.7
    LLM_DEFAULT_MAX_TOKENS: int = 1024

    # Analysis
    LLM_ANALYSIS_PROVIDER: str = ""
    LLM_ANALYSIS_API_KEY: str = ""
    LLM_ANALYSIS_MODEL: str = ""

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 30
    LLM_RATE_LIMIT_PER_MINUTE: int = 10

    # Redis
    REDIS_URL: str = ""

    # Admin features
    ADMIN_ENV_EDIT_ENABLED: bool = False
    UPDATE_AGENT_ENABLED: bool = False
    UPDATE_AGENT_TOKEN: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
