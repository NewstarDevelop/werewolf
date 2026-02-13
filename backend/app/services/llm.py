"""LLM Service - Multi-provider AI implementation with retry and fallback."""
import os
import json
import secrets
import logging
import asyncio
import re
import time
from typing import Optional, TYPE_CHECKING
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.core.config import settings, AIProviderConfig
from app.services.rate_limiter import TokenBucketLimiter, PerGameSoftLimiter, RateLimitTimeoutError
from app.services.prompts import (
    build_system_prompt,
    build_context_prompt,
    build_wolf_strategy_prompt,
)

if TYPE_CHECKING:
    from app.models.game import Game, Player

_rng = secrets.SystemRandom()

logger = logging.getLogger(__name__)

# Rate limiting configuration
INITIAL_RETRY_DELAY = 60  # Initial delay: 1 minute between first and second call
MAX_RETRY_DELAY = 180  # Maximum delay: 3 minutes
BACKOFF_INCREMENT = 60  # Add 1 minute on each failure

# Rate limiting and fairness defaults (overridable via env)
DEFAULT_MAX_WAIT_SECONDS = float(os.getenv("LLM_MAX_WAIT_SECONDS", "8"))
DEFAULT_PER_GAME_MIN_INTERVAL = float(os.getenv("LLM_PER_GAME_MIN_INTERVAL", "0.5"))
DEFAULT_PER_GAME_MAX_CONCURRENCY = int(os.getenv("LLM_PER_GAME_MAX_CONCURRENCY", "2"))

# Custom User-Agent to bypass Cloudflare bot detection
CUSTOM_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# WL-009: Input sanitization for prompt injection protection
def sanitize_text_input(text: str, max_length: int = 500) -> str:
    """
    Sanitize user-provided text to prevent prompt injection attacks.

    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text safe for LLM prompts
    """
    if not text:
        return ""

    # Limit length to prevent token exhaustion attacks
    text = str(text)[:max_length]

    # Remove potential prompt injection patterns
    # Remove system-like instructions
    dangerous_patterns = [
        r"(?i)(ignore|disregard|forget)\s+(previous|above|all|prior|earlier)\s+(instructions?|prompts?|rules?|directives?)",
        r"(?i)system\s*[:：]\s*",
        r"(?i)assistant\s*[:：]\s*",
        r"(?i)user\s*[:：]\s*",
        r"(?i)\[system\]",
        r"(?i)\[assistant\]",
        r"(?i)\[user\]",
        r"(?i)you\s+are\s+now\s+",
        r"(?i)你现在是",
        r"(?i)扮演.*AI",
        r"(?i)act\s+as\s+",
    ]

    for pattern in dangerous_patterns:
        text = re.sub(pattern, "[已过滤]", text)

    # Remove excessive newlines (potential formatting attacks)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove zero-width characters and other unicode tricks
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)

    # Escape markdown code blocks to prevent injection
    text = text.replace("```", "'''")

    return text.strip()


def validate_game_state(game: "Game") -> None:
    """
    Validate game state before using in prompts (WL-009).

    Args:
        game: Game instance to validate

    Raises:
        ValueError: If game state contains invalid data
    """
    if not game:
        raise ValueError("Game instance is None")

    if not game.id or len(game.id) > 100:
        raise ValueError("Invalid game ID")

    if game.day < 1 or game.day > 100:
        raise ValueError(f"Invalid game day: {game.day}")

    # Validate player count
    if len(game.players) < 1 or len(game.players) > 20:
        raise ValueError(f"Invalid player count: {len(game.players)}")


@dataclass
class LLMResponse:
    """Structured response from LLM."""
    thought: str
    speak: str
    action_target: Optional[int]
    raw_response: str = ""
    is_fallback: bool = False
    provider_name: str = ""


# Fallback responses for different scenarios (bilingual support)
FALLBACK_SPEECHES = {
    "zh": {
        "werewolf": [
            "我觉得场上形势不太明朗,先听听大家的意见。",
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
    },
    "en": {
        "werewolf": [
            "The situation is unclear to me, let me hear everyone's opinions first.",
            "I'm a good person, you can trust me.",
            "I don't have anything special to say, pass.",
            "I think we should consolidate our votes.",
            "This game is complex, let's analyze calmly.",
        ],
        "villager": [
            "I'm just a regular villager, no special information.",
            "Let's analyze calmly, don't vote randomly.",
            "I choose to trust the seer in the game.",
            "Pass.",
            "I don't have any special information, I'll follow the group.",
        ],
        "seer": [
            "I am the seer, please trust me.",
            "I have verification information, everyone listen to me.",
            "Please trust my verification results.",
            "I'm the real seer, the counter-claim is fake.",
            "I will use my verifications to help the village team.",
        ],
        "witch": [
            "I'm a good person, you can trust me.",
            "I have important information, but can't share now.",
            "Pass.",
            "I feel something's wrong, but need to observe more.",
            "I'm a power role, please protect me.",
        ],
        "hunter": [
            "I'm the hunter, werewolves don't target me.",
            "I have a gun, I'll take someone with me if I die.",
            "I'm a good role, you can trust me.",
            "Pass.",
            "I think the situation needs more observation.",
        ],
    },
}


class LLMService:
    """LLM service with multi-provider support, retry mechanism, and fallback."""

    def __init__(self):
        self.use_mock = settings.LLM_USE_MOCK
        self._clients: dict[str, AsyncOpenAI] = {}
        self._provider_limiters: dict[str, TokenBucketLimiter] = {}
        self._limiter_lock = asyncio.Lock()  # FIX: Lock for thread-safe limiter creation
        self._per_game_limiter = PerGameSoftLimiter(
            min_interval_seconds=DEFAULT_PER_GAME_MIN_INTERVAL,
            max_concurrency_per_game=DEFAULT_PER_GAME_MAX_CONCURRENCY,
        )
        self._max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS
        self._closed = False  # A7-FIX: Track closed state

        # Initialize clients for all configured providers
        for name, provider in settings.get_all_providers().items():
            if provider.is_valid():
                try:
                    client = AsyncOpenAI(
                        api_key=provider.api_key,
                        base_url=provider.base_url if provider.base_url else None,
                        default_headers={"User-Agent": CUSTOM_USER_AGENT},
                        timeout=120.0,  # 120 seconds timeout
                    )
                    self._clients[name] = client
                    logger.info(f"Initialized async LLM client for provider: {name} (model: {provider.model})")

                    # Create rate limiter for this provider
                    limiter = TokenBucketLimiter(
                        requests_per_minute=provider.requests_per_minute,
                        burst=provider.burst,
                        max_concurrency=provider.max_concurrency,
                    )
                    limiter._provider_name = name  # For logging
                    self._provider_limiters[name] = limiter
                    logger.info(
                        f"Rate limiter for {name}: RPM={provider.requests_per_minute}, "
                        f"concurrency={provider.max_concurrency}, burst={provider.burst}"
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize client for provider {name}: {e}")

        if not self._clients and not self.use_mock:
            logger.warning("No LLM providers configured - using mock mode")
            self.use_mock = True

    async def close(self) -> None:
        """
        A7-FIX: Close all LLM clients and release resources.

        This should be called during application shutdown to prevent
        resource leaks (unclosed httpx connection pools).
        """
        if self._closed:
            return

        self._closed = True
        close_errors = []

        for name, client in self._clients.items():
            try:
                await client.close()
                logger.debug(f"Closed LLM client for provider: {name}")
            except Exception as e:
                close_errors.append(f"{name}: {e}")
                logger.warning(f"Error closing LLM client {name}: {e}")

        self._clients.clear()
        self._provider_limiters.clear()

        if close_errors:
            logger.warning(f"LLM client cleanup completed with errors: {close_errors}")
        else:
            logger.info("LLM clients closed successfully")

    async def __aenter__(self) -> "LLMService":
        """A7-FIX: Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """A7-FIX: Async context manager exit - ensures cleanup."""
        await self.close()

    async def _get_limiter(self, provider: AIProviderConfig) -> TokenBucketLimiter:
        """Get or create rate limiter for a provider (thread-safe).

        FIX: Uses double-check locking pattern to prevent race conditions
        during concurrent limiter initialization.
        """
        # Fast path: limiter already exists
        if provider.name in self._provider_limiters:
            return self._provider_limiters[provider.name]

        # Slow path: need to create limiter with lock protection
        async with self._limiter_lock:
            # Double-check: another coroutine might have created it
            if provider.name in self._provider_limiters:
                return self._provider_limiters[provider.name]

            # Create new limiter
            limiter = TokenBucketLimiter(
                requests_per_minute=provider.requests_per_minute,
                burst=provider.burst,
                max_concurrency=provider.max_concurrency,
            )
            limiter._provider_name = provider.name
            self._provider_limiters[provider.name] = limiter
            logger.info(
                f"Dynamically created rate limiter for {provider.name}: "
                f"RPM={provider.requests_per_minute}, concurrency={provider.max_concurrency}, burst={provider.burst}"
            )
            return limiter

    def _get_client_for_player(self, seat_id: int) -> tuple[Optional[AsyncOpenAI], Optional[AIProviderConfig]]:
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

    async def _call_llm(
        self,
        client: AsyncOpenAI,
        provider: AIProviderConfig,
        system_prompt: str,
        user_prompt: str,
        *,
        game_id: Optional[str] = None,
        max_wait_seconds: Optional[float] = None,
    ) -> str:
        """Make actual LLM API call with rate limiting (WL-010: async).

        Args:
            client: The OpenAI client to use
            provider: Provider configuration
            system_prompt: System prompt for the LLM
            user_prompt: User prompt for the LLM
            game_id: Optional game ID for per-game rate limiting
            max_wait_seconds: Maximum time to wait for rate limit

        Returns:
            Raw response content from the LLM
        """
        limiter = await self._get_limiter(provider)  # FIX: Now async
        effective_wait = self._max_wait_seconds if max_wait_seconds is None else float(max_wait_seconds)

        # Build request params - don't set max_tokens to let API use default
        request_params = {
            "model": provider.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": provider.temperature,
        }

        # Apply rate limiting: per-game soft limit + provider hard limit
        # Use shared deadline to avoid wait time stacking
        start_time = time.monotonic()
        deadline = start_time + effective_wait

        if game_id:
            async with self._per_game_limiter.limit(game_id, max_wait_seconds=effective_wait):
                # Calculate remaining time for provider limiter
                remaining_wait = max(0.1, deadline - time.monotonic())
                async with limiter.limit(max_wait_seconds=remaining_wait):
                    response = await client.chat.completions.create(**request_params)
        else:
            async with limiter.limit(max_wait_seconds=effective_wait):
                response = await client.chat.completions.create(**request_params)

        # Safely extract content from response with try-except
        try:
            if response is None:
                raise ValueError("API returned None response")

            if response.choices is None or len(response.choices) == 0:
                raise ValueError("API returned empty or None choices")

            choice = response.choices[0]
            if choice is None:
                raise ValueError("API returned None choice")

            message = choice.message
            if message is None:
                raise ValueError("API returned None message")

            content = message.content
            if content is None:
                raise ValueError("API returned None content")

            logger.debug(f"LLM raw response from {provider.name}: {content}")
            return content
        except (TypeError, AttributeError) as e:
            logger.error(f"Error extracting response: {e}, response={response}")
            raise ValueError(f"Failed to extract content: {e}")

    def _parse_response(self, raw_response: str, provider_name: str = "") -> LLMResponse:
        """Parse LLM response JSON."""
        try:
            # Clean markdown code blocks if present
            cleaned_response = raw_response.strip()

            # Remove markdown code block wrapper (```json ... ``` or ``` ... ```)
            if cleaned_response.startswith("```"):
                # Find the first newline after opening ```
                first_newline = cleaned_response.find("\n")
                if first_newline != -1:
                    # Remove opening ``` and optional language identifier
                    cleaned_response = cleaned_response[first_newline + 1:]

                # Remove closing ```
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]

                cleaned_response = cleaned_response.strip()

            data = json.loads(cleaned_response)
            # Use 'or' to handle both missing keys and null values
            thought = data.get("thought") or ""
            speak = data.get("speak") or "过。"
            return LLMResponse(
                thought=thought,
                speak=speak,
                action_target=data.get("action_target"),
                raw_response=raw_response,
                is_fallback=False,
                provider_name=provider_name,
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"Original response: {raw_response[:200]}...")
            raise ValueError(f"Invalid JSON response: {raw_response[:200]}")

    def _get_fallback_response(
        self, player: "Player", action_type: str, targets: list[int] = None, language: str = "zh"
    ) -> LLMResponse:
        """Generate fallback response when LLM fails."""
        from app.i18n import normalize_language
        language = normalize_language(language)

        role = player.role.value
        lang_speeches = FALLBACK_SPEECHES.get(language, FALLBACK_SPEECHES["zh"])
        speeches = lang_speeches.get(role, lang_speeches["villager"])
        speak = _rng.choice(speeches)

        # Determine action target for non-speech actions
        action_target = None
        if action_type in ["vote", "kill", "verify", "shoot"] and targets:
            action_target = _rng.choice(targets)
        elif action_type in ["witch_save", "witch_poison"]:
            # 50% chance to use potion
            if _rng.random() < 0.5 and targets:
                action_target = targets[0] if action_type == "witch_save" else _rng.choice(targets)
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

    async def generate_response(
        self,
        player: "Player",
        game: "Game",
        action_type: str,
        targets: list[int] = None,
    ) -> LLMResponse:
        """
        Generate AI response with retry and fallback (WL-010: async).

        Args:
            player: The AI player
            game: Current game state
            action_type: Type of action (speech, vote, kill, verify, etc.)
            targets: Available target seat IDs for actions

        Returns:
            LLMResponse with thought, speak, and action_target
        """
        # WL-009: Validate game state before processing
        try:
            validate_game_state(game)
        except ValueError as e:
            logger.error(f"Invalid game state: {e}")
            return self._get_fallback_response(player, action_type, targets, language=game.language)

        # Use mock mode if configured
        if self.use_mock:
            logger.info(f"Using mock response for player {player.seat_id}")
            return self._get_fallback_response(player, action_type, targets, language=game.language)

        # Get client for this player
        client, provider = self._get_client_for_player(player.seat_id)
        if not client or not provider:
            logger.warning(f"No LLM client available for player {player.seat_id}, using fallback")
            return self._get_fallback_response(player, action_type, targets, language=game.language)

        # Build prompts (use game's language setting)
        system_prompt = build_system_prompt(player, game, language=game.language)
        context_prompt = build_context_prompt(player, game, action_type, language=game.language)

        # Add wolf strategy for werewolves (includes wolf_king and white_wolf_king)
        wolf_role_values = {"werewolf", "wolf_king", "white_wolf_king"}
        if player.role.value in wolf_role_values:
            strategy = build_wolf_strategy_prompt(player, game, language=game.language)
            if strategy:
                context_prompt = strategy + "\n" + context_prompt

        # Try with retries and exponential backoff
        last_error = None
        max_retries = max(provider.max_retries, 4)  # At least 4 retries for rate limiting

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"LLM call attempt {attempt + 1} for player {player.seat_id} "
                    f"using provider {provider.name} (model: {provider.model})"
                )

                raw_response = await self._call_llm(
                    client, provider, system_prompt, context_prompt,
                    game_id=game.id,
                    max_wait_seconds=self._max_wait_seconds,
                )
                response = self._parse_response(raw_response, provider.name)

                # Validate action_target if needed
                if action_type in ["vote", "kill", "verify", "shoot"]:
                    if response.action_target is not None and targets:
                        if response.action_target not in targets and response.action_target != 0:
                            logger.warning(
                                f"Invalid target {response.action_target}, expected one of {targets}"
                            )
                            response.action_target = _rng.choice(targets)

                # Safe logging with None check for speak
                speak_preview = (response.speak or "")[:50]
                logger.info(
                    f"LLM response for player {player.seat_id} from {provider.name}: "
                    f"{speak_preview}..."
                )
                return response

            except RateLimitTimeoutError as e:
                # Rate limiter timeout - go directly to fallback without retry
                logger.warning(
                    f"Rate limiter timeout for player {player.seat_id} "
                    f"(provider={provider.name}, game={game.id}): {e}"
                )
                return self._get_fallback_response(player, action_type, targets, language=game.language)

            except Exception as e:
                last_error = e
                logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")

                # Apply linear backoff for rate limiting (403 errors)
                # First retry: 60s, then add 60s each time, max 180s
                if "403" in str(e) or "blocked" in str(e).lower() or "rate" in str(e).lower():
                    delay = min(INITIAL_RETRY_DELAY + (BACKOFF_INCREMENT * attempt), MAX_RETRY_DELAY)
                    logger.info(f"Rate limited, waiting {delay}s before retry...")
                    await asyncio.sleep(delay)  # WL-010: Use async sleep
                elif attempt < max_retries - 1:
                    # Longer delay for truncation errors
                    await asyncio.sleep(5)  # WL-010: Use async sleep

        # All retries failed, use fallback
        logger.error(f"All LLM retries failed for player {player.seat_id}: {last_error}")
        return self._get_fallback_response(player, action_type, targets, language=game.language)

    # ==================== Convenience Methods ====================

    async def generate_speech(self, player: "Player", game: "Game") -> str:
        """Generate speech for an AI player (WL-010: async)."""
        response = await self.generate_response(player, game, "speech")
        return response.speak

    async def decide_kill_target(
        self, player: "Player", game: "Game", targets: list[int]
    ) -> int:
        """Decide who to kill as werewolf (WL-010: async)."""
        response = await self.generate_response(player, game, "kill", targets)
        return response.action_target if response.action_target else _rng.choice(targets)

    async def decide_verify_target(
        self, player: "Player", game: "Game", targets: list[int]
    ) -> int:
        """Decide who to verify as seer (WL-010: async)."""
        response = await self.generate_response(player, game, "verify", targets)
        return response.action_target if response.action_target else _rng.choice(targets)

    async def decide_witch_action(self, player: "Player", game: "Game") -> dict:
        """Decide witch action (save/poison) with value calculation (WL-010: async)."""
        result = {"save": False, "poison_target": None}

        # First check if should save
        if player.has_save_potion and game.night_kill_target:
            # Calculate save value
            save_value = self._calculate_save_value(game, game.night_kill_target)

            # High-value targets (revealed seer) must be saved
            if save_value >= 80:
                result["save"] = True
                return result  # Can't use both in same night

            # For medium-value targets, let LLM decide
            response = await self.generate_response(
                player, game, "witch_save", [game.night_kill_target, 0]
            )
            if response.action_target == game.night_kill_target:
                result["save"] = True
                return result  # Can't use both in same night

        # Then check if should poison
        if player.has_poison_potion:
            alive_others = [
                p.seat_id for p in game.get_alive_players()
                if p.seat_id != player.seat_id
            ]
            if alive_others:
                response = await self.generate_response(
                    player, game, "witch_poison", alive_others + [0]
                )
                if response.action_target and response.action_target != 0:
                    result["poison_target"] = response.action_target

        return result

    def _calculate_save_value(self, game: "Game", target_id: int) -> int:
        """Calculate the value of saving a target (0-100)."""
        target = game.players.get(target_id)
        if not target:
            return 0

        # Revealed seer is highest priority
        if target.role.value == "seer":
            # Check if seer has revealed (claimed in messages)
            for msg in game.messages:
                if msg.seat_id == target_id:
                    content = msg.content.lower()
                    seer_patterns = ["我是预言家", "i am the seer", "i'm the seer", "本预言家"]
                    if any(pattern in content for pattern in seer_patterns):
                        return 100  # Must save revealed seer

        # Check if target is suspected wolf (don't save)
        # This is a simplified check - could be enhanced with voting pattern analysis
        wolf_suspicion = 0
        for action in game.actions:
            if action.action_type.value == "vote" and action.target_id == target_id:
                wolf_suspicion += 1

        if wolf_suspicion >= 3:  # Many people voted for them
            return 0  # Likely wolf, don't save

        # Default value for unknown players
        return 50

    async def decide_vote_target(
        self, player: "Player", game: "Game", targets: list[int]
    ) -> int:
        """Decide who to vote for (WL-010: async)."""
        response = await self.generate_response(player, game, "vote", targets + [0])
        return response.action_target if response.action_target is not None else _rng.choice(targets)

    async def decide_shoot_target(
        self, player: "Player", game: "Game", targets: list[int]
    ) -> Optional[int]:
        """Decide who to shoot as hunter (WL-010: async)."""
        response = await self.generate_response(player, game, "shoot", targets + [0])
        if response.action_target and response.action_target != 0:
            return response.action_target
        return None

    # Legacy method for compatibility
    def generate_player_action(self, system_prompt: str, context: str) -> dict:
        """Legacy method - returns mock decision data."""
        return {
            "thought": "我是AI，正在思考中...",
            "speak": "我是AI，以后再说。",
            "action_target": None,
        }
