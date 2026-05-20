"""OpenAI LLM provider."""

from __future__ import annotations

import os
from .base import LLMProvider, LLMResponse

from openai import AsyncOpenAI, OpenAI


class OpenAIProvider(LLMProvider):
    """LLM provider for OpenAI models (GPT-4o, etc.)."""

    def __init__(self, api_key: str | None = None):
        super().__init__(api_key)
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY not set")
        self._client = OpenAI(api_key=key)
        self._async_client = AsyncOpenAI(api_key=key)

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        response = await self._async_client.chat.completions.create(
            model=model,
            messages=full_messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        return LLMResponse(
            text=choice.message.content or "",
            model=response.model,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason or "stop",
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
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        response = self._client.chat.completions.create(
            model=model,
            messages=full_messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        return LLMResponse(
            text=choice.message.content or "",
            model=response.model,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason or "stop",
        )
