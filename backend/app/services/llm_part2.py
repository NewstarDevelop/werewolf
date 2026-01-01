"""Deprecated module.

This file previously contained an incomplete/partial implementation that caused
syntax errors. The active implementation lives in `app.services.llm`.

Kept for backwards compatibility with any external imports.
"""

from app.services.llm import LLMService, LLMResponse

__all__ = ["LLMService", "LLMResponse"]
