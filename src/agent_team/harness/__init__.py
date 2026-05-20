"""Harness模块 — Agent工程保障层。

每个Agent配备:
- Guardrails: 输入/输出/工具调用校验
- Tracing: 可追踪的span
- Handoffs: Agent间交接过滤
- State Machine: 可恢复可重放的状态机
- Human-in-the-Loop: 审核/暂停/恢复

参考:
- OpenAI Agents SDK: guardrails, tool guardrails, tracing, handoffs
- Temporal: 可恢复/可重放workflow
- LangGraph: human-in-the-loop, interrupt/resume
"""

from .guardrails import Guardrail, InputGuardrail, OutputGuardrail, ToolGuardrail, GuardrailResult
from .tracing import TraceSpan, Tracer, trace_agent_call
from .handoffs import HandoffFilter, AgentHandoff, handoff_registry
from .state_machine import (
    WorkflowStateMachine, PhaseState, WorkflowStatus,
    Checkpoint, recover_workflow, replay_workflow,
)
from .human_loop import HumanApproval, ApprovalGate, pause_for_approval
from .contract import ContractVerifier, CoverageReport, Requirement

__all__ = [
    # Guardrails
    "Guardrail", "InputGuardrail", "OutputGuardrail", "ToolGuardrail", "GuardrailResult",
    # Tracing
    "TraceSpan", "Tracer", "trace_agent_call",
    # Handoffs
    "HandoffFilter", "AgentHandoff", "handoff_registry",
    # State Machine
    "WorkflowStateMachine", "PhaseState", "WorkflowStatus",
    "Checkpoint", "recover_workflow", "replay_workflow",
    # Human-in-the-loop
    "HumanApproval", "ApprovalGate", "pause_for_approval",
]
