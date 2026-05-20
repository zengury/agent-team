"""DeepSeek LLM provider — OpenAI-compatible API."""

from __future__ import annotations

import os
from .base import LLMProvider, LLMResponse

from openai import AsyncOpenAI, OpenAI


class DeepSeekProvider(LLMProvider):
    """LLM provider for DeepSeek (OpenAI-compatible API)."""

    BASE_URL = "https://api.deepseek.com/v1"
    DEFAULT_MODEL = "deepseek-chat"

    def __init__(self, api_key: str | None = None):
        super().__init__(api_key)
        key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise ValueError("DEEPSEEK_API_KEY not set")
        self._client = OpenAI(api_key=key, base_url=self.BASE_URL)
        self._async_client = AsyncOpenAI(api_key=key, base_url=self.BASE_URL)

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        model: str = "",
        temperature: float = 0.4,
        max_tokens: int = 4096,
        tools: list | None = None,
    ) -> LLMResponse:
        model = model or self.DEFAULT_MODEL
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        kwargs = {
            "model": model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        response = await self._async_client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
        choice = response.choices[0]
        # Handle reasoning models: content may be empty, use reasoning_content
        text = choice.message.content or ""
        if not text and hasattr(choice.message, 'reasoning_content') and choice.message.reasoning_content:
            text = "[思考]\n" + choice.message.reasoning_content
        tool_calls = []
        if choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in choice.message.tool_calls
            ]
        return LLMResponse(
            text=choice.message.content or "",
            model=response.model,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason or "stop",
            tool_calls=tool_calls,
        )

    def chat_sync(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        model: str = "",
        temperature: float = 0.4,
        max_tokens: int = 4096,
        tools: list | None = None,
    ) -> LLMResponse:
        model = model or self.DEFAULT_MODEL
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        kwargs = {
            "model": model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        response = self._client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
        choice = response.choices[0]
        # Handle reasoning models
        text = choice.message.content or ""
        if not text and hasattr(choice.message, 'reasoning_content') and choice.message.reasoning_content:
            text = "[思考]\n" + choice.message.reasoning_content
        tool_calls = []
        if choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in choice.message.tool_calls
            ]
        return LLMResponse(
            text=choice.message.content or "",
            model=response.model,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason or "stop",
            tool_calls=tool_calls,
        )
