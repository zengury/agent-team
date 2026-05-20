"""Tracing — Span-based可追踪Agent调用链。

参考: OpenAI Agents SDK tracing, Temporal tracing.

每个Agent调用生成一个span:
- span_id: 唯一标识
- parent_span_id: 父span(委派来源)
- agent_name: 哪个Agent
- input/output: 输入输出快照
- guardrail_results: 校验结果
- timing: 开始/结束时间
- metadata: 自定义标签

所有span组成一棵调用树，可导出为JSON供UI展示。
"""

from __future__ import annotations

import json
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Iterator


@dataclass
class TraceSpan:
    """单个追踪span."""
    span_id: str
    agent_name: str
    phase_name: str
    operation: str  # "execute", "delegate", "chat", "tool_call"
    
    # Timing
    start_time: str = ""
    end_time: str = ""
    duration_ms: float = 0.0
    
    # I/O
    input_preview: str = ""       # 输入摘要(前500字符)
    output_preview: str = ""      # 输出摘要(前500字符)
    input_tokens: int = 0
    output_tokens: int = 0
    
    # Hierarchy
    parent_span_id: str = ""
    child_spans: list[str] = field(default_factory=list)
    
    # Status
    status: str = "pending"  # pending | running | success | error | blocked
    error_message: str = ""
    
    # Guardrails
    guardrail_checks: list[dict] = field(default_factory=list)
    
    # Metadata
    metadata: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


class Tracer:
    """
    追踪器 — 管理所有span，构建调用树。
    
    用法:
        tracer = Tracer()
        
        async with tracer.span("wukong", "开发", "execute") as span:
            span.input_preview = task[:500]
            # ... Agent执行 ...
            span.output_preview = output[:500]
            span.status = "success"
        
        # 导出
        tree = tracer.export_tree()
    """

    def __init__(self, storage_path: str | Path | None = None):
        self._spans: dict[str, TraceSpan] = {}
        self._current_spans: list[str] = []  # 当前span栈
        self.storage_path = Path(storage_path) if storage_path else None
        
        # 持久化
        if self.storage_path:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def current_span_id(self) -> str | None:
        return self._current_spans[-1] if self._current_spans else None

    def start_span(
        self,
        agent_name: str,
        phase_name: str,
        operation: str = "execute",
        metadata: dict | None = None,
        tags: list[str] | None = None,
    ) -> TraceSpan:
        """手动开始一个span."""
        span = TraceSpan(
            span_id=f"span_{uuid.uuid4().hex[:12]}",
            agent_name=agent_name,
            phase_name=phase_name,
            operation=operation,
            parent_span_id=self.current_span_id or "",
            start_time=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
            tags=tags or [],
        )
        
        # 关联父子
        if self.current_span_id:
            parent = self._spans.get(self.current_span_id)
            if parent:
                parent.child_spans.append(span.span_id)
        
        self._spans[span.span_id] = span
        self._current_spans.append(span.span_id)
        span.status = "running"
        return span

    def end_span(self, span_id: str, status: str = "success", error: str = ""):
        """结束一个span."""
        if span_id not in self._spans:
            return
        
        span = self._spans[span_id]
        span.status = status
        span.error_message = error
        span.end_time = datetime.now(timezone.utc).isoformat()
        
        if span.start_time:
            start = datetime.fromisoformat(span.start_time)
            end = datetime.fromisoformat(span.end_time)
            span.duration_ms = (end - start).total_seconds() * 1000
        
        # 从栈中移除
        if self._current_spans and self._current_spans[-1] == span_id:
            self._current_spans.pop()

    @asynccontextmanager
    async def span(
        self,
        agent_name: str,
        phase_name: str,
        operation: str = "execute",
        metadata: dict | None = None,
    ) -> AsyncIterator[TraceSpan]:
        """异步上下文管理器 — 自动开始/结束span."""
        s = self.start_span(agent_name, phase_name, operation, metadata)
        try:
            yield s
            if s.status == "running":
                self.end_span(s.span_id, "success")
        except Exception as e:
            self.end_span(s.span_id, "error", str(e))
            raise

    @contextmanager
    def span_sync(
        self,
        agent_name: str,
        phase_name: str,
        operation: str = "execute",
        metadata: dict | None = None,
    ) -> Iterator[TraceSpan]:
        """同步上下文管理器."""
        s = self.start_span(agent_name, phase_name, operation, metadata)
        try:
            yield s
            if s.status == "running":
                self.end_span(s.span_id, "success")
        except Exception as e:
            self.end_span(s.span_id, "error", str(e))
            raise

    def add_guardrail_check(self, span_id: str, check: dict):
        """给span添加guardrail校验记录."""
        if span_id in self._spans:
            self._spans[span_id].guardrail_checks.append(check)

    def get_span(self, span_id: str) -> TraceSpan | None:
        return self._spans.get(span_id)

    def get_tree(self, span_id: str | None = None) -> dict:
        """获取以某span为根的调用树(JSON可序列化)."""
        if span_id is None:
            # 找根span(没有parent的)
            roots = [s for s in self._spans.values() if not s.parent_span_id]
            if not roots:
                return {}
            span_id = roots[0].span_id
        
        span = self._spans.get(span_id)
        if not span:
            return {}
        
        return {
            "span_id": span.span_id,
            "agent": span.agent_name,
            "phase": span.phase_name,
            "operation": span.operation,
            "status": span.status,
            "duration_ms": span.duration_ms,
            "input_preview": span.input_preview[:200],
            "output_preview": span.output_preview[:200],
            "input_tokens": span.input_tokens,
            "output_tokens": span.output_tokens,
            "error": span.error_message,
            "guardrails": span.guardrail_checks,
            "tags": span.tags,
            "children": [self.get_tree(cid) for cid in span.child_spans],
        }

    def export_json(self, path: str | Path | None = None) -> str:
        """导出所有span为JSON."""
        data = {
            "workflow_id": getattr(self, "workflow_id", "unknown"),
            "spans": {
                sid: {
                    "agent": s.agent_name,
                    "phase": s.phase_name,
                    "operation": s.operation,
                    "status": s.status,
                    "start": s.start_time,
                    "end": s.end_time,
                    "duration_ms": s.duration_ms,
                    "parent": s.parent_span_id,
                    "input_preview": s.input_preview[:300],
                    "output_preview": s.output_preview[:300],
                    "tokens": {"in": s.input_tokens, "out": s.output_tokens},
                    "guardrails": s.guardrail_checks,
                    "error": s.error_message,
                    "tags": s.tags,
                }
                for sid, s in self._spans.items()
            },
            "tree": self.get_tree(),
        }
        
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        
        if path:
            Path(path).write_text(json_str)
        elif self.storage_path:
            self.storage_path.write_text(json_str)
        
        return json_str

    def get_summary(self) -> dict:
        """获取追踪摘要."""
        total = len(self._spans)
        success = sum(1 for s in self._spans.values() if s.status == "success")
        error = sum(1 for s in self._spans.values() if s.status == "error")
        total_tokens = sum(s.input_tokens + s.output_tokens for s in self._spans.values())
        total_duration = sum(s.duration_ms for s in self._spans.values())
        
        return {
            "total_spans": total,
            "success": success,
            "error": error,
            "total_tokens": total_tokens,
            "total_duration_ms": total_duration,
            "agents": list(set(s.agent_name for s in self._spans.values())),
        }


# ── Decorator ──────────────────────────────────────────

def trace_agent_call(agent_name: str, phase_name: str = ""):
    """
    装饰器 — 自动追踪Agent调用。
    
    用法:
        @trace_agent_call("wukong", "开发")
        async def implement(task, workspace):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tracer = _get_current_tracer()
            if tracer:
                async with tracer.span(agent_name, phase_name, "execute") as span:
                    span.input_preview = str(args)[:500]
                    result = await func(*args, **kwargs)
                    span.output_preview = str(result)[:500]
                    return result
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# ── Global Tracer ──────────────────────────────────────

_tracer: Tracer | None = None


def get_tracer(storage_path: str | Path | None = None) -> Tracer:
    global _tracer
    if _tracer is None:
        _tracer = Tracer(storage_path)
    return _tracer


def _get_current_tracer() -> Tracer | None:
    return _tracer


def reset_tracer():
    global _tracer
    _tracer = None
