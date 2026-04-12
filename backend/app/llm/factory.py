import logging

from app.llm.client import JSONModeClient, LLMProvider
from app.llm.fallback import FallbackLLMClient
from app.llm.local_provider import LocalRuleBasedProvider
from app.llm.openai_provider import (
    OpenAICompatibleProvider,
    load_openai_compatible_settings_from_env,
)

logger = logging.getLogger(__name__)


def build_llm_provider_from_env() -> LLMProvider:
    settings = load_openai_compatible_settings_from_env()
    if settings is None:
        logger.info("using local rule-based llm provider")
        return LocalRuleBasedProvider()

    logger.info(
        "using openai-compatible llm provider model=%s base_url=%s",
        settings.model,
        settings.base_url,
    )
    return OpenAICompatibleProvider(settings=settings)


def build_default_llm_client() -> FallbackLLMClient:
    return FallbackLLMClient(
        client=JSONModeClient(provider=build_llm_provider_from_env()),
    )
