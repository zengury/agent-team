"""Base agent class and agent registry."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..llm import LLMProvider, LLMResponse, get_provider
from ..tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for a single agent."""
    name: str
    role: str
    model: str
    provider: str
    temperature: float = 0.4
    max_tokens: int = 4096
    system_prompt: str = ""
    description: str = ""
    emoji: str = "🤖"
    color: str = "#888888"
    personality: str = ""


@dataclass
class Task:
    """A task assigned by Elon to a specialized agent."""
    task_id: str
    agent_name: str  # "jobs" | "linux" | "turing" | "bezos"
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | running | done | failed
    output: str = ""


class BaseAgent:
    """Base class for all specialized agents. Supports function calling."""

    MAX_TOOL_ROUNDS = 10  # 最多工具调用轮数

    def __init__(self, config: AgentConfig, llm: LLMProvider | None = None,
                 tool_registry: ToolRegistry | None = None):
        self.config = config
        self._llm = llm
        self._conversation: list[dict[str, Any]] = []
        self.tool_registry = tool_registry

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = get_provider(self.config.provider)
        return self._llm

    def reset_conversation(self):
        """Clear conversation history for a fresh task."""
        self._conversation = []

    async def execute(self, task: Task, workspace: Path) -> str:
        """
        Execute a task with function calling support.
        
        If tool_registry is available, the LLM can call tools to read/write files,
        run commands, etc. The loop continues until the LLM returns a text response
        without tool calls.
        """
        self.reset_conversation()
        self._conversation.append({"role": "user", "content": task.description})
        
        tools = self.tool_registry.tool_schemas if self.tool_registry else None
        accumulated_text = []
        
        for round_num in range(self.MAX_TOOL_ROUNDS):
            response = await self.llm.chat(
                system_prompt=self.config.system_prompt,
                messages=self._conversation,
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                tools=tools,
            )
            
            # Collect text
            if response.text:
                accumulated_text.append(response.text)
            
            # Check for tool calls
            if response.tool_calls and self.tool_registry:
                for tc in response.tool_calls:
                    fn_name = tc["function"]["name"]
                    raw_args = tc["function"]["arguments"]
                    
                    # Robust JSON parsing for DeepSeek tool calls
                    try:
                        fn_args = json.loads(raw_args)
                    except Exception:
                        fn_args = {}
                        # Extract params from malformed JSON using regex
                        import re as _re2
                        # Extract 'path'
                        pm = _re2.search(r'"path"\s*:\s*"([^"]+)"', raw_args)
                        if pm: fn_args['path'] = pm.group(1)
                        # Extract 'content' - more complex, look for content field
                        cm = _re2.search(r'"content"\s*:\s*"', raw_args)
                        if cm:
                            start = cm.end()
                            # Find the matching end quote before "} or ,
                            end_m = _re2.search(r'"(\s*[,}])', raw_args[start:])
                            if end_m:
                                fn_args['content'] = raw_args[start:start + end_m.start()]
                        # Extract 'command'
                        cmd_m = _re2.search(r'"command"\s*:\s*"([^"]+)"', raw_args)
                        if cmd_m: fn_args['command'] = cmd_m.group(1)
                        if fn_args:
                            logger.info(f"Repaired {fn_name}: {list(fn_args.keys())}")
                        else:
                            logger.warning(f"Cannot parse tool args: {raw_args[:200]}")
                    
                    logger.info(f"{self.name} 调用工具: {fn_name}({fn_args})")
                    
                    # Execute tool
                    result = await self.tool_registry.execute(fn_name, fn_args)
                    
                    # Add assistant message with tool_call (preserve reasoning_content for deepseek-v4)
                    assistant_msg = {
                        "role": "assistant",
                        "content": response.text or "",
                        "tool_calls": [{
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": fn_name, "arguments": tc["function"]["arguments"]},
                        }],
                    }
                    if response.reasoning_content:
                        assistant_msg["reasoning_content"] = response.reasoning_content
                    self._conversation.append(assistant_msg)
                    # Add tool result
                    self._conversation.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result[:4000],  # Truncate long results
                    })
                
                continue  # Next round to process tool results
            
            # No tool calls → done
            break
        
        full_output = "\n\n".join(accumulated_text)
        return full_output

    def execute_sync(self, task: Task, workspace: Path) -> str:
        """Synchronous version of execute."""
        self._conversation.append({"role": "user", "content": task.description})
        
        response = self.llm.chat_sync(
            system_prompt=self.config.system_prompt,
            messages=self._conversation,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        
        self._conversation.append({"role": "assistant", "content": response.text})
        return response.text

    def chat(self, message: str) -> str:
        """One-shot chat without task overhead. Returns response text."""
        self._conversation.append({"role": "user", "content": message})
        response = self.llm.chat_sync(
            system_prompt=self.config.system_prompt,
            messages=self._conversation,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        self._conversation.append({"role": "assistant", "content": response.text})
        return response.text

    async def achat(self, message: str) -> str:
        """Async one-shot chat."""
        self._conversation.append({"role": "user", "content": message})
        response = await self.llm.chat(
            system_prompt=self.config.system_prompt,
            messages=self._conversation,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        self._conversation.append({"role": "assistant", "content": response.text})
        return response.text
