"""OpenAI LLM adapter."""

from __future__ import annotations

from job_search_agent.llm.base import LLMProvider
from job_search_agent.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI API adapter."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.model = model
        try:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("OpenAI package required. Install with: pip install openai") from None

    @property
    def name(self) -> str:
        return "openai"

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("openai_error", error=str(e))
            return f"[OpenAI error: {e}]"

    async def close(self) -> None:
        if hasattr(self._client, "close"):
            await self._client.close()
