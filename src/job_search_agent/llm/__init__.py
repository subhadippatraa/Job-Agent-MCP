"""LLM integration — optional enhancement layer."""

from __future__ import annotations

from job_search_agent.config import get_settings
from job_search_agent.llm.base import LLMProvider, NoLLMProvider


def get_llm_provider() -> LLMProvider:
    """Get the configured LLM provider, or NoLLMProvider if none configured."""
    settings = get_settings()

    if settings.llm_provider == "openai" and settings.openai_api_key:
        from job_search_agent.llm.openai import OpenAIProvider
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        from job_search_agent.llm.anthropic import AnthropicProvider
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )

    return NoLLMProvider()


__all__ = ["LLMProvider", "NoLLMProvider", "get_llm_provider"]
