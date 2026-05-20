"""可恢复工作流状态机。

参考: Temporal workflow state machine + LangGraph interrupt/resume.

核心能力:
- 每个phase是一个状态节点
- 状态转换可追踪、可重放
- 失败后可恢复(从最近的checkpoint)
- 支持Human-in-the-loop暂停/审核/恢复
- Checkpoint持久化到磁盘

设计原则:
- 每个phase执行前自动存档checkpoint
- 失败时不中断整个workflow，而是触发弹性策略
- 支持: retry, skip, fallback, escalate, rollback
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"         # 暂停(等待人工审核)
    RETRYING = "retrying"     # 重试中
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PhaseStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"  # 等待人工审核
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    FALLBACK = "fallback"    # 使用降级方案完成


@dataclass
class Checkpoint:
    """工作流检查点 — 可序列化存档."""
    checkpoint_id: str
    workflow_id: str
    workflow_name: str
    phase_name: str           # 即将执行的phase
    completed_phases: list[str]
    phase_results: dict[str, dict]  # phase_name → {status, output_preview, ...}
    state_snapshot: dict      # 项目状态快照(project_name, workspace等)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    retry_count: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class PhaseState:
    """单个phase的执行状态."""
    name: str
    agent_name: str
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: str = ""
    finished_at: str = ""
    output: str = ""
    error: str = ""
    retry_count: int = 0
    max_retries: int = 2
    depends_on: list[str] = field(default_factory=list)
    optional: bool = False
    
    # 弹性策略
    on_failure: str = "stop"   # stop | retry | skip | fallback | escalate
    fallback_agent: str = ""   # 降级时用的Agent
    fallback_action: str = ""


class WorkflowStateMachine:
    """
    工作流状态机 — 可恢复、可重放、可追踪。
    
    用法:
        sm = WorkflowStateMachine(workflow_def, workspace)
        
        # 从头执行
        await sm.run(team)
        
        # 崩溃后恢复
        sm = WorkflowStateMachine.load_from_checkpoint(workspace)
        await sm.resume(team)
        
        # 重放(只读验证)
        await sm.replay(team)
    """

    def __init__(
        self,
        workflow_name: str,
        phases: list[dict],
        workspace: Path,
        state_dir: str | Path | None = None,
    ):
        self.workflow_name = workflow_name
        self.workspace = workspace
        self.state_dir = Path(state_dir) if state_dir else workspace / ".workflow_state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.status: WorkflowStatus = WorkflowStatus.PENDING
        self.workflow_id = f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(self):x}"
        
        # 构建phase状态
        self.phases: dict[str, PhaseState] = {}
        self._phase_order: list[str] = []
        
        for p in phases:
            ps = PhaseState(
                name=p["name"],
                agent_name=p["agent"],
                depends_on=p.get("depends_on", []),
                optional=p.get("optional", False),
            )
            self.phases[p["name"]] = ps
            self._phase_order.append(p["name"])
        
        # Checkpoints
        self._checkpoints: list[Checkpoint] = []
        self._current_phase: str | None = None
        
        # Human-in-the-loop
        self._approval_gates: dict[str, bool] = {}  # phase_name → requires_approval
    
    # ── Phase迭代 ─────────────────────────────────────

    @property
    def current_phase(self) -> str | None:
        return self._current_phase

    @property
    def completed_phases(self) -> list[str]:
        return [
            name for name, ps in self.phases.items()
            if ps.status in (PhaseStatus.COMPLETED, PhaseStatus.SKIPPED, PhaseStatus.FALLBACK)
        ]

    @property
    def failed_phases(self) -> list[str]:
        return [name for name, ps in self.phases.items() if ps.status == PhaseStatus.FAILED]

    def next_phase(self) -> str | None:
        """获取下一个待执行的phase(按依赖顺序)."""
        for name in self._phase_order:
            ps = self.phases[name]
            if ps.status in (PhaseStatus.PENDING, PhaseStatus.AWAITING_APPROVAL):
                # 检查依赖
                if all(
                    self.phases[dep].status in (PhaseStatus.COMPLETED, PhaseStatus.SKIPPED, PhaseStatus.FALLBACK)
                    for dep in ps.depends_on
                ):
                    return name
        return None

    def require_approval(self, phase_name: str):
        """标记某个phase需要人工审核才能通过."""
        self._approval_gates[phase_name] = True
        if phase_name in self.phases:
            self.phases[phase_name].on_failure = "stop"

    def approve_phase(self, phase_name: str):
        """人工审核通过."""
        self._approval_gates[phase_name] = False
        if phase_name in self.phases:
            ps = self.phases[phase_name]
            if ps.status == PhaseStatus.AWAITING_APPROVAL:
                ps.status = PhaseStatus.COMPLETED
                ps.finished_at = datetime.now().isoformat()

    def reject_phase(self, phase_name: str, reason: str = ""):
        """人工审核驳回."""
        if phase_name in self.phases:
            ps = self.phases[phase_name]
            ps.status = PhaseStatus.FAILED
            ps.error = f"人工审核驳回: {reason}"
            ps.finished_at = datetime.now().isoformat()

    # ── Checkpoint ─────────────────────────────────────

    def save_checkpoint(self) -> Checkpoint:
        """保存当前状态为checkpoint."""
        cp = Checkpoint(
            checkpoint_id=f"cp_{len(self._checkpoints):04d}",
            workflow_id=self.workflow_id,
            workflow_name=self.workflow_name,
            phase_name=self._current_phase or "",
            completed_phases=self.completed_phases,
            phase_results={
                name: {
                    "status": ps.status.value,
                    "agent": ps.agent_name,
                    "output_preview": ps.output[:500] if ps.output else "",
                    "error": ps.error,
                    "retry_count": ps.retry_count,
                }
                for name, ps in self.phases.items()
            },
            state_snapshot={
                "workspace": str(self.workspace),
                "status": self.status.value,
                "approval_gates": self._approval_gates.copy(),
            },
        )
        
        self._checkpoints.append(cp)
        
        # 持久化到磁盘
        cp_path = self.state_dir / f"{cp.checkpoint_id}.json"
        cp_path.write_text(json.dumps({
            "checkpoint_id": cp.checkpoint_id,
            "workflow_id": cp.workflow_id,
            "workflow_name": cp.workflow_name,
            "phase_name": cp.phase_name,
            "completed_phases": cp.completed_phases,
            "phase_results": cp.phase_results,
            "state_snapshot": cp.state_snapshot,
            "timestamp": cp.timestamp,
            "retry_count": cp.retry_count,
        }, ensure_ascii=False, indent=2))
        
        logger.info(f"Checkpoint saved: {cp.checkpoint_id} at phase '{cp.phase_name}'")
        return cp

    @classmethod
    def load_from_checkpoint(cls, workspace: Path, workflow_def: dict | None = None) -> WorkflowStateMachine | None:
        """
        从checkpoint恢复状态机。
        
        Args:
            workspace: 工作区路径
            workflow_def: 工作流定义(可选，自动推导)
        """
        state_dir = workspace / ".workflow_state"
        if not state_dir.exists():
            return None
        
        checkpoints = sorted(state_dir.glob("cp_*.json"))
        if not checkpoints:
            return None
        
        # 加载最新的checkpoint
        latest = checkpoints[-1]
        data = json.loads(latest.read_text())
        
        # 重建phase列表
        # 需要workflow_def来获取完整phase信息
        if workflow_def is None:
            # 尝试从checkpoint重建
            phases = [
                {"name": name, "agent": info["agent"]}
                for name, info in data["phase_results"].items()
            ]
        else:
            phases = workflow_def["phases"]
        
        sm = cls(
            workflow_name=data["workflow_name"],
            phases=phases,
            workspace=workspace,
            state_dir=state_dir,
        )
        
        # 恢复状态
        sm.workflow_id = data["workflow_id"]
        sm.status = WorkflowStatus(data["state_snapshot"].get("status", "paused"))
        
        for name, info in data["phase_results"].items():
            if name in sm.phases:
                sm.phases[name].status = PhaseStatus(info["status"])
                sm.phases[name].output = info.get("output_preview", "")
                sm.phases[name].error = info.get("error", "")
                sm.phases[name].retry_count = info.get("retry_count", 0)
        
        sm._approval_gates = data["state_snapshot"].get("approval_gates", {})
        sm._current_phase = data["phase_name"]
        
        logger.info(f"Workflow restored from checkpoint: {data['checkpoint_id']}")
        logger.info(f"  Status: {sm.status.value}, Completed: {sm.completed_phases}")
        
        return sm

    # ── 执行 ───────────────────────────────────────────

    async def execute_phase(self, phase_name: str, execute_fn, context: dict | None = None) -> dict:
        """
        执行单个phase(带弹性策略)。
        
        Args:
            phase_name: phase名称
            execute_fn: async (phase_name, agent_name, context) → (output, success)
            context: 执行上下文
        
        Returns:
            {status, output, error, retries}
        """
        ps = self.phases[phase_name]
        self._current_phase = phase_name
        ps.status = PhaseStatus.RUNNING
        ps.started_at = datetime.now().isoformat()
        self.status = WorkflowStatus.RUNNING
        
        # 执行前存档
        self.save_checkpoint()
        
        # 检查是否需要人工审核
        if self._approval_gates.get(phase_name):
            ps.status = PhaseStatus.AWAITING_APPROVAL
            self.status = WorkflowStatus.PAUSED
            logger.info(f"Phase '{phase_name}' 等待人工审核...")
            return {"status": "awaiting_approval", "phase": phase_name}
        
        # 执行(带重试)
        ctx = context or {}
        ctx["retry_count"] = 0
        ctx["max_retries"] = ps.max_retries
        
        while ps.retry_count <= ps.max_retries:
            try:
                output, success = await execute_fn(phase_name, ps.agent_name, ctx)
                
                if success:
                    ps.status = PhaseStatus.COMPLETED
                    ps.output = output
                    ps.finished_at = datetime.now().isoformat()
                    self.save_checkpoint()
                    return {"status": "completed", "output": output, "retries": ps.retry_count}
                else:
                    # 执行完成但返回了失败标记
                    ps.retry_count += 1
                    ctx["retry_count"] = ps.retry_count
                    logger.warning(f"Phase '{phase_name}' 返回失败(attempt {ps.retry_count}): {output[:200]}")
                    if ps.retry_count <= ps.max_retries:
                        self.status = WorkflowStatus.RETRYING
                        time.sleep(1)  # 短暂退避
                    
            except Exception as e:
                ps.retry_count += 1
                ctx["retry_count"] = ps.retry_count
                logger.error(f"Phase '{phase_name}' 异常(attempt {ps.retry_count}): {e}")
                if ps.retry_count <= ps.max_retries:
                    self.status = WorkflowStatus.RETRYING
                    time.sleep(ps.retry_count)  # 递增退避
        
        # 超过最大重试 → 弹性策略
        ps.status = PhaseStatus.FAILED
        ps.error = f"超过最大重试次数({ps.max_retries})"
        ps.finished_at = datetime.now().isoformat()
        
        strategy = ps.on_failure
        logger.warning(f"Phase '{phase_name}' 失败，策略: {strategy}")
        
        if strategy == "skip":
            ps.status = PhaseStatus.SKIPPED
            self.save_checkpoint()
            return {"status": "skipped", "reason": "failure_policy:skip"}
        
        elif strategy == "retry":
            self.status = WorkflowStatus.RETRYING
            self.save_checkpoint()
            return {"status": "retrying", "retries": ps.retry_count}
        
        elif strategy == "fallback":
            # 使用降级Agent重试
            if ps.fallback_agent:
                logger.info(f"使用降级Agent: {ps.fallback_agent}")
                try:
                    output, success = await execute_fn(phase_name, ps.fallback_agent, ctx)
                    if success:
                        ps.status = PhaseStatus.FALLBACK
                        ps.output = output
                        ps.finished_at = datetime.now().isoformat()
                        self.save_checkpoint()
                        return {"status": "fallback", "output": output}
                except Exception as e:
                    logger.error(f"降级也失败: {e}")
        
        # stop / escalate: 标记为失败，停止workflow
        self.status = WorkflowStatus.FAILED
        self.save_checkpoint()
        return {"status": "failed", "error": ps.error}

    async def resume(self, execute_fn, context: dict | None = None) -> dict:
        """
        从当前状态恢复执行。
        
        Args:
            execute_fn: async (phase_name, agent_name, context) → (output, success)
            context: 执行上下文
        
        Returns:
            最终状态摘要
        """
        if self.status == WorkflowStatus.COMPLETED:
            return {"status": "already_completed"}
        
        # 处理等待审核的phase
        for name, ps in self.phases.items():
            if ps.status == PhaseStatus.AWAITING_APPROVAL:
                if not self._approval_gates.get(name):
                    # 已被批准，标记完成
                    ps.status = PhaseStatus.COMPLETED
                    ps.finished_at = datetime.now().isoformat()
        
        # 继续执行
        while True:
            next_p = self.next_phase()
            if next_p is None:
                break
            
            result = await self.execute_phase(next_p, execute_fn, context)
            
            if result["status"] == "awaiting_approval":
                self.status = WorkflowStatus.PAUSED
                return {"status": "paused", "phase": next_p}
            
            if result["status"] == "failed":
                self.status = WorkflowStatus.FAILED
                return {"status": "failed", "phase": next_p, "error": result.get("error", "")}
        
        # 全部完成
        self.status = WorkflowStatus.COMPLETED
        self._current_phase = None
        self.save_checkpoint()
        return {"status": "completed", "completed_phases": len(self.completed_phases)}

    # ── 审计 ───────────────────────────────────────────

    def audit_trail(self) -> list[dict]:
        """生成审计追踪."""
        return [
            {
                "checkpoint_id": cp.checkpoint_id,
                "timestamp": cp.timestamp,
                "phase_at_checkpoint": cp.phase_name,
                "completed_count": len(cp.completed_phases),
                "retry_count": cp.retry_count,
            }
            for cp in self._checkpoints
        ]

    def get_status_summary(self) -> dict:
        """获取状态摘要(用于UI展示)."""
        phases_summary = {}
        for name, ps in self.phases.items():
            phases_summary[name] = {
                "agent": ps.agent_name,
                "status": ps.status.value,
                "retries": ps.retry_count,
                "duration": "",
            }
            if ps.started_at and ps.finished_at:
                start = datetime.fromisoformat(ps.started_at)
                end = datetime.fromisoformat(ps.finished_at)
                phases_summary[name]["duration"] = f"{(end-start).total_seconds():.1f}s"
        
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "current_phase": self._current_phase,
            "completed": len(self.completed_phases),
            "total": len(self.phases),
            "checkpoints": len(self._checkpoints),
            "phases": phases_summary,
        }


# ── 恢复 / 重放工具函数 ────────────────────────────────

async def recover_workflow(workspace: Path, execute_fn, workflow_def: dict | None = None) -> dict:
    """
    从checkpoint恢复并继续执行工作流。
    
    用法:
        result = await recover_workflow(
            workspace=Path("workspaces/acme-corp"),
            execute_fn=my_execute_function,
        )
    """
    sm = WorkflowStateMachine.load_from_checkpoint(workspace, workflow_def)
    if sm is None:
        return {"status": "no_checkpoint", "message": "未找到checkpoint，请从头开始"}
    
    logger.info(f"恢复工作流: {sm.workflow_name} (已完成 {len(sm.completed_phases)}/{len(sm.phases)} phases)")
    return await sm.resume(execute_fn)


async def replay_workflow(workspace: Path) -> dict:
    """
    重放工作流执行记录(只读，不实际执行)。
    用于审计和调试。
    """
    sm = WorkflowStateMachine.load_from_checkpoint(workspace)
    if sm is None:
        return {"status": "no_checkpoint"}
    
    return {
        "workflow_id": sm.workflow_id,
        "workflow_name": sm.workflow_name,
        "status": sm.status.value,
        "audit_trail": sm.audit_trail(),
        "phases": {
            name: ps.status.value
            for name, ps in sm.phases.items()
        },
    }
