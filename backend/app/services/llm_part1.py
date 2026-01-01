"""LLM Service - Multi-provider AI implementation with retry and fallback."""
import json
import random
import logging
import time
from typing import Optional, TYPE_CHECKING
from dataclasses import dataclass

from openai import OpenAI
import httpx

from app.core.config import settings, AIProviderConfig
from app.services.prompts import (
    build_system_prompt,
    build_context_prompt,
    build_wolf_strategy_prompt,
)

if TYPE_CHECKING:
    from app.models.game import Game, Player

logger = logging.getLogger(__name__)

# Rate limiting configuration
INITIAL_RETRY_DELAY = 60  # Initial delay: 1 minute between first and second call
MAX_RETRY_DELAY = 180  # Maximum delay: 3 minutes
BACKOFF_INCREMENT = 60  # Add 1 minute on each failure

# Custom User-Agent to bypass Cloudflare bot detection
CUSTOM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


@dataclass
class LLMResponse:
    """Structured response from LLM."""
    thought: str
    speak: str
    action_target: Optional[int]
    raw_response: str = ""
    is_fallback: bool = False
    provider_name: str = ""


# Fallback responses for different scenarios
FALLBACK_SPEECHES = {
    "werewolf": [
        "我觉得场上形势不太明朗，先听听大家的意见。",
        "我是好人，大家可以相信我。",
        "我没什么特别想说的，过。",
        "我觉得我们应该把票集中一下。",
        "这局形势很复杂，大家冷静分析。",
    ],
    "villager": [
        "我是普通村民，没有什么特殊信息。",
        "大家冷静分析一下，不要乱投。",
        "我选择相信场上的预言家。",
        "过。",
        "我没有什么特别的信息，听大家的。",
    ],
    "seer": [
        "我是预言家，请大家相信我。",
        "我手里有验人信息，大家听我说。",
        "请大家相信我的查验结果。",
        "我是真预言家，对跳的是假的。",
        "我会用我的查验帮助好人阵营。",
    ],
    "witch": [
        "我是好人，大家可以信任我。",
        "我手里有重要信息，但现在不方便说。",
        "过。",
        "我觉得场上有问题，但需要再观察。",
        "我是神职，请大家保护我。",
    ],
    "hunter": [
        "我是猎人，狼人不要点我。",
        "我有枪，死了会带走一个。",
        "我是好人牌，大家可以相信我。",
        "过。",
        "我觉得场上形势还需要观察。",
    ],
}


class LLMService:
    """LLM service with multi-provider support, retry mechanism, and fallback."""

    def __init__(self):
        self.use_mock = settings.LLM_USE_MOCK
        self._clients: dict[str, OpenAI] = {}

        # Create custom httpx client with browser User-Agent
        custom_http_client = httpx.Client(
            headers={"User-Agent": CUSTOM_USER_AGENT},
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

        # Initialize clients for all configured providers
        for name, provider in settings.get_all_providers().items():
            if provider.is_valid():
                try:
                    client = OpenAI(
                        api_key=provider.api_key,
                        base_url=provider.base_url if provider.base_url else None,
                        http_client=custom_http_client,
                    )
                    self._clients[name] = client
                    logger.info(f"Initialized LLM client for provider: {name} (model: {provider.model})")
                except Exception as e:
                    logger.error(f"Failed to initialize client for provider {name}: {e}")

        if not self._clients and not self.use_mock:
            logger.warning("No LLM providers configured - using mock mode")
            self.use_mock = True

    def _get_client_for_player(self, seat_id: int) -> tuple[Optional[OpenAI], Optional[AIProviderConfig]]:
        """Get the appropriate client and config for a player."""
        provider = settings.get_provider_for_player(seat_id)
        if provider and provider.name in self._clients:
            return self._clients[provider.name], provider

        # Fallback to default
        if "default" in self._clients:
            return self._clients["default"], settings.get_provider("default")

        # Try any available client
        for name, client in self._clients.items():
            provider = settings.get_provider(name)
            if provider:
                return client, provider

        return None, None

    def _call_llm(
        self,
        client: OpenAI,
        provider: AIProviderConfig,
        system_prompt: str,
        user_prompt: str
    ) -> str:
        """Make actual LLM API call."""
        response = client.chat.completions.create(
            model=provider.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=provider.temperature,
            max_tokens=provider.max_tokens,
        )

        content = response.choices[0].message.content
        logger.debug(f"LLM raw response from {provider.name}: {content}")
        return content or ""

    def _parse_response(self, raw_response: str, provider_name: str = "") -> LLMResponse:
        """Parse LLM response JSON."""
        try:
            data = json.loads(raw_response)
            return LLMResponse(
                thought=data.get("thought", ""),
                speak=data.get("speak", "过。"),
                action_target=data.get("action_target"),
                raw_response=raw_response,
                is_fallback=False,
                provider_name=provider_name,
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise ValueError(f"Invalid JSON response: {raw_response}")

    def _get_fallback_response(
        self, player: "Player", action_type: str, targets: list[int] = None
    ) -> LLMResponse:
        """Generate fallback response when LLM fails."""
        role = player.role.value
        speeches = FALLBACK_SPEECHES.get(role, FALLBACK_SPEECHES["villager"])
        speak = random.choice(speeches)

        # Determine action target for non-speech actions
        action_target = None
        if action_type in ["vote", "kill", "verify", "shoot"] and targets:
            action_target = random.choice(targets)
        elif action_type in ["witch_save", "witch_poison"]:
            # 50% chance to use potion
            if random.random() < 0.5 and targets:
                action_target = targets[0] if action_type == "witch_save" else random.choice(targets)
            else:
                action_target = 0  # Skip

        return LLMResponse(
            thought="（AI回退模式）",
            speak=speak if action_type == "speech" else "",
            action_target=action_target,
            raw_response="",
            is_fallback=True,
            provider_name="fallback",
        )
