"""LLM provider abstraction layer."""

from __future__ import annotations

from .base import LLMProvider, LLMResponse
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider
from .deepseek_provider import DeepSeekProvider


def get_provider(name: str, api_key: str | None = None) -> LLMProvider:
    """Factory: return the right LLM provider by name."""
    name = name.lower()
    if name == "anthropic":
        return AnthropicProvider(api_key=api_key)
    elif name == "openai":
        return OpenAIProvider(api_key=api_key)
    elif name == "deepseek":
        return DeepSeekProvider(api_key=api_key)
    else:
        raise ValueError(f"Unknown provider: {name}")


__all__ = ["LLMProvider", "LLMResponse", "AnthropicProvider", "OpenAIProvider", "DeepSeekProvider", "get_provider"]
