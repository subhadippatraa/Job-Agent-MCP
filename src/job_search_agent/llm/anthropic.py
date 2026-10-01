"""Anthropic LLM adapter."""

from __future__ import annotations

from typing import Any

from job_search_agent.llm.base import LLMProvider
from job_search_agent.logging import get_logger

logger = get_logger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic API adapter."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        try:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=api_key)
        except ImportError:
            raise ImportError(
                "Anthropic package required. Install with: pip install anthropic"
            ) from None

    @property
    def name(self) -> str:
        return "anthropic"

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> str:
        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }
            if system:
                kwargs["system"] = system

            response = await self._client.messages.create(**kwargs)
            return response.content[0].text if response.content else ""
        except Exception as e:
            logger.error("anthropic_error", error=str(e))
            return f"[Anthropic error: {e}]"

    async def close(self) -> None:
        if hasattr(self._client, "close"):
            await self._client.close()
