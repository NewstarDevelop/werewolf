"""OpenAI-compatible LLM client.

Supports OpenAI, Anthropic (OpenAI-compat endpoint), DeepSeek,
and any custom endpoint that follows the /v1/chat/completions protocol.
"""

from __future__ import annotations

import json
import logging

import httpx

from app.services.llm.base import LLMClient

logger = logging.getLogger(__name__)

# Default timeout for LLM requests
_REQUEST_TIMEOUT = 60.0  # seconds


class OpenAICompatClient(LLMClient):
    """Universal client for any OpenAI-compatible API endpoint.

    Works with:
    - OpenAI (api.openai.com)
    - DeepSeek (api.deepseek.com)
    - Anthropic via OpenAI-compat layer (api.anthropic.com/v1)
    - Any custom /v1/chat/completions endpoint
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.default_temperature = temperature
        self.default_max_tokens = max_tokens

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a free-form text completion via OpenAI-compatible API."""
        response = await self._call_api(
            messages,
            temperature=temperature or self.default_temperature,
            max_tokens=max_tokens or self.default_max_tokens,
        )
        return response

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """Generate a structured JSON completion.

        Uses the API's response_format={"type": "json_object"} when supported,
        otherwise falls back to manual JSON parsing.
        """
        response = await self._call_api(
            messages,
            temperature=temperature or self.default_temperature,
            max_tokens=max_tokens or self.default_max_tokens,
            json_mode=True,
        )
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON, attempting repair: %s", response[:200])
            # Try to extract JSON from markdown code blocks
            import re
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
            if match:
                return json.loads(match.group(1).strip())
            raise ValueError(f"LLM returned invalid JSON: {response[:200]}")

    async def _call_api(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
    ) -> str:
        """Make the actual HTTP request to the LLM API."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            logger.debug("LLM request to %s, model=%s", url, self.model)
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()

            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # Log token usage if available
            usage = data.get("usage")
            if usage:
                logger.debug(
                    "LLM token usage: prompt=%s, completion=%s",
                    usage.get("prompt_tokens", "?"),
                    usage.get("completion_tokens", "?"),
                )

            return content
