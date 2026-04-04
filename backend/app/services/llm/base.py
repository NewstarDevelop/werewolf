"""Abstract base class for LLM clients."""

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Base class for all LLM provider clients.

    All providers must implement `complete` (free-form text)
    and `complete_json` (structured JSON output).
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a free-form text completion.

        Args:
            messages: OpenAI-style message list [{"role": "system"|"user"|"assistant", "content": "..."}]
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text content
        """
        ...

    @abstractmethod
    async def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict:
        """Generate a structured JSON completion.

        The response must be valid JSON. If the provider returns
        malformed JSON, this method should raise.

        Args:
            messages: OpenAI-style message list
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Parsed JSON dict
        """
        ...
