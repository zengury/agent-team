"""Anthropic (Claude) LLM provider."""

from __future__ import annotations

import os
from .base import LLMProvider, LLMResponse

import anthropic


class AnthropicProvider(LLMProvider):
    """LLM provider for Anthropic Claude models."""

    def __init__(self, api_key: str | None = None):
        super().__init__(api_key)
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self._client = anthropic.Anthropic(api_key=key)
        self._async_client = anthropic.AsyncAnthropic(api_key=key)

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        # Anthropic expects messages without system — system goes in create()
        user_messages = [m for m in messages if m["role"] != "system"]
        response = await self._async_client.messages.create(
            model=model,
            system=system_prompt,
            messages=user_messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return LLMResponse(
            text=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            finish_reason=response.stop_reason or "stop",
        )

    def chat_sync(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        user_messages = [m for m in messages if m["role"] != "system"]
        response = self._client.messages.create(
            model=model,
            system=system_prompt,
            messages=user_messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return LLMResponse(
            text=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            finish_reason=response.stop_reason or "stop",
        )
