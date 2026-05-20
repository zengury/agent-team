"""Guardrails — 输入/输出/工具调用三层校验。

参考: OpenAI Agents SDK guardrails & tool guardrails.

架构:
  输入 → [InputGuardrail] → Agent执行 → [OutputGuardrail] → 输出
                          └─ 工具调用 → [ToolGuardrail] ─┘
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class GuardrailResult:
    """校验结果."""
    passed: bool
    message: str = ""
    filtered_output: str | None = None
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class Guardrail(ABC):
    """Guardrail基类."""
    
    name: str = "base_guardrail"
    
    @abstractmethod
    async def check(self, content: str, context: dict | None = None) -> GuardrailResult:
        ...


# ── Input Guardrails ─────────────────────────────────

class InputGuardrail(Guardrail):
    """
    输入校验 — 在Agent接收输入前执行。
    
    检查项:
    - 内容长度是否在限制内
    - 是否包含禁止关键词(PII泄露, 敏感词)
    - 上下文是否完整(必要条件检查)
    - Token预算是否超限
    """

    def __init__(
        self,
        max_length: int = 50000,
        forbidden_patterns: list[str] | None = None,
        required_context_keys: list[str] | None = None,
        max_tokens_estimate: int = 16000,
    ):
        self.max_length = max_length
        self.forbidden_patterns = forbidden_patterns or []
        self.required_context_keys = required_context_keys or []
        self.max_tokens_estimate = max_tokens_estimate

    async def check(self, content: str, context: dict | None = None) -> GuardrailResult:
        issues = []
        
        # Length check
        if len(content) > self.max_length:
            issues.append(f"内容过长: {len(content)} > {self.max_length} 字符")
        
        # Forbidden patterns
        for pattern in self.forbidden_patterns:
            if pattern.lower() in content.lower():
                issues.append(f"包含禁止模式: {pattern}")
        
        # Required context keys
        if context and self.required_context_keys:
            missing = [k for k in self.required_context_keys if k not in context]
            if missing:
                issues.append(f"缺少必要上下文: {missing}")
        
        # Token estimate
        estimated_tokens = len(content) // 3  # 粗略估计
        if estimated_tokens > self.max_tokens_estimate:
            issues.append(f"预估Token超限: {estimated_tokens} > {self.max_tokens_estimate}")
        
        if issues:
            return GuardrailResult(
                passed=False,
                message="; ".join(issues),
                metadata={"issues": issues},
            )
        
        return GuardrailResult(passed=True, message="输入校验通过")


class PIIGuardrail(InputGuardrail):
    """PII(个人身份信息)防护 — 检测并警告敏感信息."""
    
    # 常见PII模式
    PII_PATTERNS = [
        "身份证", "身份证号", "ID number",
        "银行卡", "bank card", "credit card",
        "密码", "password", "passwd",
        "手机号", "phone number",
        "家庭地址", "home address",
    ]

    def __init__(self, block_on_pii: bool = False):
        super().__init__(forbidden_patterns=self.PII_PATTERNS)
        self.block_on_pii = block_on_pii

    async def check(self, content: str, context: dict | None = None) -> GuardrailResult:
        result = await super().check(content, context)
        if not result.passed and self.block_on_pii:
            result.filtered_output = "[PII检测: 内容包含敏感信息，已拦截]"
        return result


# ── Output Guardrails ─────────────────────────────────

class OutputGuardrail(Guardrail):
    """
    输出校验 — 在Agent产出后执行。
    
    检查项:
    - 输出是否为空
    - 是否包含预期格式(JSON/Markdown/Code)
    - 是否满足最小长度要求
    - Token/字符利用率
    """

    def __init__(
        self,
        min_length: int = 10,
        required_format: str | None = None,  # "json", "markdown", "code"
        validate_schema: dict | None = None,
    ):
        self.min_length = min_length
        self.required_format = required_format
        self.validate_schema = validate_schema

    async def check(self, content: str, context: dict | None = None) -> GuardrailResult:
        issues = []
        
        # Empty check
        if not content or not content.strip():
            return GuardrailResult(passed=False, message="输出为空")
        
        # Min length
        if len(content.strip()) < self.min_length:
            issues.append(f"输出过短: {len(content)} < {self.min_length} 字符")
        
        # Format check
        if self.required_format == "json":
            try:
                # Try to find JSON in the output
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    json.loads(json_match.group())
                else:
                    issues.append("输出中未找到有效JSON")
            except json.JSONDecodeError as e:
                issues.append(f"JSON格式错误: {e}")
        
        elif self.required_format == "markdown":
            if not any(marker in content for marker in ["#", "##", "```", "- ", "1. "]):
                issues.append("输出可能不是Markdown格式")
        
        if issues:
            return GuardrailResult(
                passed=False,
                message="; ".join(issues),
                metadata={"issues": issues},
            )
        
        return GuardrailResult(passed=True, message="输出校验通过")


# ── Tool Guardrails ───────────────────────────────────

class ToolGuardrail(Guardrail):
    """
    工具调用包装 — 在Agent调用工具前后执行。
    
    功能:
    - 工具调用前: 参数校验
    - 工具调用后: 结果校验
    - 超时控制
    - 重试策略
    - 降级处理
    """

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        fallback_handler: Callable | None = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.fallback_handler = fallback_handler

    async def check(self, content: str, context: dict | None = None) -> GuardrailResult:
        # Tool guardrails are invoked differently — see wrap_tool_call()
        return GuardrailResult(passed=True, message="工具校验就绪")

    async def wrap_tool_call(
        self, tool_name: str, tool_fn: Callable, *args, **kwargs
    ) -> tuple[Any, GuardrailResult]:
        """包装工具调用，带超时、重试、降级."""
        import asyncio
        
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    asyncio.ensure_future(tool_fn(*args, **kwargs))
                    if asyncio.iscoroutinefunction(tool_fn)
                    else asyncio.get_event_loop().run_in_executor(None, tool_fn, *args, **kwargs),
                    timeout=self.timeout_seconds,
                )
                return result, GuardrailResult(
                    passed=True,
                    message=f"工具 {tool_name} 调用成功",
                    metadata={"attempt": attempt + 1, "tool": tool_name},
                )
            except asyncio.TimeoutError:
                last_error = f"工具 {tool_name} 超时 ({self.timeout_seconds}s)"
                logger.warning(f"Attempt {attempt + 1}: {last_error}")
            except Exception as e:
                last_error = f"工具 {tool_name} 错误: {e}"
                logger.warning(f"Attempt {attempt + 1}: {last_error}")
            
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        # Fallback
        if self.fallback_handler:
            try:
                fallback_result = await self.fallback_handler(tool_name, *args, **kwargs)
                return fallback_result, GuardrailResult(
                    passed=True,
                    message=f"工具 {tool_name} 使用降级方案",
                    metadata={"fallback": True},
                )
            except Exception as e:
                pass
        
        return None, GuardrailResult(
            passed=False,
            message=last_error or "工具调用失败",
            metadata={"tool": tool_name, "attempts": self.max_retries + 1},
        )


# ── Composite Guardrail ───────────────────────────────

class CompositeGuardrail(Guardrail):
    """组合多个guardrail，全部通过才算通过."""

    def __init__(self, guardrails: list[Guardrail], mode: str = "all"):
        """
        Args:
            guardrails: 子guardrail列表
            mode: "all"(全部通过) | "any"(任一通过) | "soft"(记录但不拦截)
        """
        self.guardrails = guardrails
        self.mode = mode

    async def check(self, content: str, context: dict | None = None) -> GuardrailResult:
        results = []
        for gr in self.guardrails:
            result = await gr.check(content, context)
            results.append(result)
        
        if self.mode == "all":
            failed = [r for r in results if not r.passed]
            if failed:
                return GuardrailResult(
                    passed=False,
                    message="; ".join(r.message for r in failed),
                    metadata={"failed_count": len(failed), "results": results},
                )
            return GuardrailResult(passed=True, message="全部校验通过", metadata={"count": len(results)})
        
        elif self.mode == "any":
            passed = [r for r in results if r.passed]
            if passed:
                return GuardrailResult(passed=True, message="至少一项通过")
            return GuardrailResult(passed=False, message="全部校验失败")
        
        else:  # soft mode
            failed = [r for r in results if not r.passed]
            return GuardrailResult(
                passed=True,  # soft mode always passes
                message=f"软校验完成 ({len(failed)} 项有问题但不拦截)",
                metadata={"warnings": [r.message for r in failed]},
            )
