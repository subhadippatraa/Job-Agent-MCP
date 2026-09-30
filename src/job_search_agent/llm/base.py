"""LLM abstraction — base class for optional LLM integration."""

from __future__ import annotations

import abc
from typing import Optional


class LLMProvider(abc.ABC):
    """Abstract base for LLM providers.

    The core system works without an LLM. These are optional enhancements for:
    - Complex requirement extraction from job descriptions
    - Semantic comparison when keyword matching is insufficient
    - Application preparation (recruiter messages, cover letter points)
    - JD summarization
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'openai', 'anthropic')."""
        ...

    @abc.abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> str:
        """Generate a completion."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        pass


class NoLLMProvider(LLMProvider):
    """Stub provider when no LLM is configured.

    Returns a message indicating LLM is not available.
    """

    @property
    def name(self) -> str:
        return "none"

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> str:
        return "[LLM not configured — this feature requires an API key. Set LLM_PROVIDER and the corresponding API key in .env]"
