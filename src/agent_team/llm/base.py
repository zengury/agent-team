"""Base LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    text: str
    model: str
    usage: dict = field(default_factory=dict)  # {"input_tokens": N, "output_tokens": N}
    finish_reason: str = "stop"
    tool_calls: list = field(default_factory=list)
    reasoning_content: str = ""  # For reasoning models (deepseek-v4-pro)


class LLMProvider(ABC):
    """Abstract base for LLM providers (Anthropic, OpenAI, local, etc.)."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    @abstractmethod
    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 4096,
        tools: list | None = None,
    ) -> LLMResponse:
        """Send a chat completion request. Returns standardized response."""
        ...

    @abstractmethod
    def chat_sync(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Synchronous version of chat."""
        ...
