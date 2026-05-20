"""Handoffs — Agent间交接过滤。

参考: OpenAI Agents SDK handoffs, input filtering.

当Agent A产出被传递给Agent B时:
1. Input Filter: 过滤/转换A的输出为B的输入
2. Context Injection: 注入B需要的上下文
3. Format Adaptation: 格式适配(JSON→Markdown等)

关键原则:
- 不让Agent A的技术细节泄露给Agent B(需要清理)
- 确保B获得B需要的信息(不能丢失)
- 保留溯源链(知道信息从哪来)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


@dataclass
class HandoffRecord:
    """交接记录."""
    from_agent: str
    to_agent: str
    original_output: str
    filtered_input: str
    filters_applied: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class HandoffFilter:
    """
    交接过滤器 — 在Agent间传递信息时清洗和适配。
    
    流程:
        Agent A output → [Strip tech details] → [Inject context] → [Format adapt] → Agent B input
    """

    def __init__(self, name: str = "default_handoff"):
        self.name = name
        self._filters: list[Callable[[str, dict], str]] = []
        self._context_providers: list[Callable[[str, dict], str]] = []

    def add_filter(self, fn: Callable[[str, dict], str]) -> HandoffFilter:
        """添加过滤函数 fn(output_text, context) → filtered_text."""
        self._filters.append(fn)
        return self

    def add_context(self, fn: Callable[[str, dict], str]) -> HandoffFilter:
        """添加上下文注入函数 fn(current_text, context) → enriched_text."""
        self._context_providers.append(fn)
        return self

    async def process(self, output: str, from_agent: str, to_agent: str,
                      context: dict | None = None) -> tuple[str, HandoffRecord]:
        """执行完整的交接处理."""
        ctx = context or {}
        ctx["from_agent"] = from_agent
        ctx["to_agent"] = to_agent
        
        filtered = output
        applied = []
        
        # 应用过滤
        for fn in self._filters:
            filtered = fn(filtered, ctx)
            applied.append(fn.__name__ if hasattr(fn, '__name__') else 'filter')
        
        # 注入上下文
        for fn in self._context_providers:
            filtered = fn(filtered, ctx)
            applied.append(fn.__name__ if hasattr(fn, '__name__') else 'context')
        
        record = HandoffRecord(
            from_agent=from_agent,
            to_agent=to_agent,
            original_output=output[:500],
            filtered_input=filtered[:500],
            filters_applied=applied,
        )
        
        return filtered, record


class AgentHandoff:
    """
    Agent交接管理器 — 管理所有Agent对之间的交接规则。
    
    用法:
        handoff = AgentHandoff()
        
        # 定义 八戒→悟空 的交接
        handoff.register("bajie", "wukong",
            strip_tech_details,
            inject_architecture_context,
        )
        
        # 执行交接
        wukong_input = await handoff.handoff("bajie", "wukong", bajie_output)
    """

    def __init__(self):
        self._registry: dict[str, HandoffFilter] = {}

    def _key(self, from_agent: str, to_agent: str) -> str:
        return f"{from_agent}→{to_agent}"

    def register(self, from_agent: str, to_agent: str,
                 *filters_and_contexts: Callable) -> HandoffFilter:
        """注册一对Agent的交接规则."""
        hf = HandoffFilter(f"{from_agent}→{to_agent}")
        for fn in filters_and_contexts:
            # 根据命名约定区分 filter vs context
            name = fn.__name__ if hasattr(fn, '__name__') else ''
            if 'filter' in name or 'strip' in name or 'clean' in name:
                hf.add_filter(fn)
            else:
                hf.add_context(fn)
        self._registry[self._key(from_agent, to_agent)] = hf
        return hf

    def get(self, from_agent: str, to_agent: str) -> HandoffFilter | None:
        return self._registry.get(self._key(from_agent, to_agent))

    async def handoff(self, from_agent: str, to_agent: str,
                      output: str, context: dict | None = None) -> tuple[str, HandoffRecord | None]:
        """执行一次Agent交接."""
        hf = self.get(from_agent, to_agent)
        if hf is None:
            # 如果没注册，使用默认处理
            hf = HandoffFilter(f"default:{from_agent}→{to_agent}")
            hf.add_filter(_default_cleanup)
        
        return await hf.process(output, from_agent, to_agent, context)


# ── 预定义过滤函数 ─────────────────────────────────────

def _default_cleanup(text: str, ctx: dict) -> str:
    """默认清理: 移除过长的代码块和技术细节."""
    # 如果太长，截取关键部分
    if len(text) > 8000:
        # 保留开头和结尾
        head = text[:3000]
        tail = text[-2000:]
        return f"{head}\n\n... [中间省略 {len(text)-5000} 字符] ...\n\n{tail}"
    return text


def strip_implementation_details(text: str, ctx: dict) -> str:
    """
    从代码实现的输出中提取给测试/文档的信息。
    保留: 功能描述, API接口, 配置说明
    移除: 具体代码实现细节
    """
    lines = text.split('\n')
    filtered = []
    in_code_block = False
    for line in lines:
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            filtered.append(line)
            continue
        if in_code_block:
            # 保留import和函数签名，跳过实现体
            if any(kw in line for kw in ['import ', 'from ', 'def ', 'class ', 'async def ']):
                filtered.append(line)
            elif not line.strip():
                filtered.append(line)
            elif len(filtered) > 2 and filtered[-1].strip() == '':
                filtered.append('# ... (实现省略)')
            continue
        filtered.append(line)
    return '\n'.join(filtered)


def inject_test_context(text: str, ctx: dict) -> str:
    """给沙僧注入测试所需上下文."""
    header = "📋 测试任务上下文:\n"
    if ctx.get("prd_summary"):
        header += f"- PRD摘要: {ctx['prd_summary'][:200]}\n"
    if ctx.get("acceptance_criteria"):
        header += f"- 验收标准: {ctx['acceptance_criteria']}\n"
    return header + "\n---\n\n" + text


def inject_client_context(text: str, ctx: dict) -> str:
    """给白龙马注入客户上下文."""
    header = "🐉 客户文档任务:\n"
    header += "请用非技术语言撰写，面向企业主。\n"
    header += "关注业务价值，不写技术实现细节。\n\n"
    return header + "---\n\n" + text


# ── 全局注册表 ─────────────────────────────────────────

handoff_registry = AgentHandoff()
