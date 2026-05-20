"""Human-in-the-loop — 审核/暂停/恢复。

参考: LangGraph human-in-the-loop, interrupt/resume.

支持模式:
- 审批门(Approval Gate): 关键phase执行前暂停等人工确认
- 中断恢复(Interrupt/Resume): 任何时候可以暂停/恢复workflow
- 审核面板: 展示待审批内容供人类决策
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class ApprovalDecision(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"     # 修改后重试
    SKIP = "skip"         # 跳过此phase


@dataclass
class ApprovalRequest:
    """人工审核请求."""
    request_id: str
    workflow_id: str
    phase_name: str
    agent_name: str
    description: str
    input_preview: str       # Agent将接收的输入摘要
    expected_output: str     # 期望产出描述
    context: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"  # pending | approved | rejected | modified
    decision: str = ""
    decision_note: str = ""


class ApprovalGate:
    """
    审批门 — 管理所有审核请求。
    
    用法:
        gate = ApprovalGate()
        
        # 请求审批
        req = gate.request(workflow_id, phase_name, agent_name, 
                          description, input_preview, expected_output)
        
        # 获取待审批列表
        pending = gate.pending()
        
        # 审批(通常在UI中操作)
        gate.approve(req.request_id, "可以执行")
        gate.reject(req.request_id, "需求理解有偏差，请重新分析")
    """

    def __init__(self, storage_path: str | Path | None = None):
        self._requests: dict[str, ApprovalRequest] = {}
        self._history: list[ApprovalRequest] = []
        self.storage_path = Path(storage_path) if storage_path else None
        self._counter = 0
        
        # Callbacks
        self._on_approve: list[Callable] = []
        self._on_reject: list[Callable] = []

    def on_approve(self, fn: Callable):
        """审批通过时的回调."""
        self._on_approve.append(fn)

    def on_reject(self, fn: Callable):
        """审批驳回时的回调."""
        self._on_reject.append(fn)

    def request(
        self,
        workflow_id: str,
        phase_name: str,
        agent_name: str,
        description: str,
        input_preview: str = "",
        expected_output: str = "",
        context: dict | None = None,
    ) -> ApprovalRequest:
        """创建一个审核请求."""
        self._counter += 1
        req = ApprovalRequest(
            request_id=f"ar_{self._counter:04d}",
            workflow_id=workflow_id,
            phase_name=phase_name,
            agent_name=agent_name,
            description=description,
            input_preview=input_preview,
            expected_output=expected_output,
            context=context or {},
        )
        self._requests[req.request_id] = req
        self._save()
        return req

    def pending(self) -> list[ApprovalRequest]:
        """获取所有待审批请求."""
        return [r for r in self._requests.values() if r.status == "pending"]

    def approve(self, request_id: str, note: str = "") -> ApprovalRequest:
        """审批通过."""
        req = self._requests.get(request_id)
        if req is None:
            raise ValueError(f"审批请求不存在: {request_id}")
        
        req.status = "approved"
        req.decision = "approve"
        req.decision_note = note
        
        self._history.append(req)
        del self._requests[request_id]
        
        for fn in self._on_approve:
            try:
                fn(req)
            except Exception as e:
                pass
        
        self._save()
        return req

    def reject(self, request_id: str, reason: str = "") -> ApprovalRequest:
        """审批驳回."""
        req = self._requests.get(request_id)
        if req is None:
            raise ValueError(f"审批请求不存在: {request_id}")
        
        req.status = "rejected"
        req.decision = "reject"
        req.decision_note = reason
        
        self._history.append(req)
        del self._requests[request_id]
        
        for fn in self._on_reject:
            try:
                fn(req)
            except Exception as e:
                pass
        
        self._save()
        return req

    def get_history(self, limit: int = 50) -> list[ApprovalRequest]:
        return self._history[-limit:]

    def _save(self):
        if self.storage_path:
            data = {
                "pending": {
                    rid: {
                        "phase": r.phase_name,
                        "agent": r.agent_name,
                        "description": r.description,
                        "status": r.status,
                        "timestamp": r.timestamp,
                    }
                    for rid, r in self._requests.items()
                },
                "history_count": len(self._history),
            }
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


class HumanApproval:
    """
    人工审核管理器 — 集成ApprovalGate与workflow。
    
    用法:
        ha = HumanApproval()
        
        # 注册需要审核的phase
        ha.require_approval_for("定方向")   # 唐僧分析后要审核
        ha.require_approval_for("出主意")   # 八戒PRD要审核
        
        # 在phase执行前检查
        if ha.needs_approval("定方向"):
            # 暂停，等待UI中的审核操作
            await ha.wait_for_approval("定方向", timeout=3600)
    """

    def __init__(self, storage_path: str | Path | None = None):
        self.gate = ApprovalGate(storage_path)
        self._required_phases: set[str] = set()
        self._waiters: dict[str, asyncio.Event] = {}

    def require_approval_for(self, phase_name: str):
        """标记某个phase需要人工审核."""
        self._required_phases.add(phase_name)

    def needs_approval(self, phase_name: str) -> bool:
        return phase_name in self._required_phases

    async def wait_for_approval(
        self,
        phase_name: str,
        workflow_id: str = "",
        agent_name: str = "",
        description: str = "",
        input_preview: str = "",
        expected_output: str = "",
        timeout: float | None = 3600,
    ) -> ApprovalDecision:
        """
        暂停并等待人工审核。
        
        返回: APPROVE / REJECT / MODIFY / SKIP
        """
        if phase_name not in self._waiters:
            self._waiters[phase_name] = asyncio.Event()
        
        # 创建审核请求
        req = self.gate.request(
            workflow_id=workflow_id,
            phase_name=phase_name,
            agent_name=agent_name,
            description=description,
            input_preview=input_preview,
            expected_output=expected_output,
        )
        
        # 注册回调：当审批完成后触发event
        event = self._waiters[phase_name]
        event.clear()
        
        def _on_complete(completed_req):
            if completed_req.request_id == req.request_id:
                event.set()
        
        self.gate.on_approve(_on_complete)
        self.gate.on_reject(_on_complete)
        
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            updated_req = next(
                (r for r in self.gate.get_history() if r.request_id == req.request_id),
                None,
            )
            if updated_req and updated_req.status == "approved":
                return ApprovalDecision.APPROVE
            else:
                return ApprovalDecision.REJECT
        except asyncio.TimeoutError:
            return ApprovalDecision.SKIP  # 超时自动跳过


# ── 便捷函数 ───────────────────────────────────────────

async def pause_for_approval(
    phase_name: str,
    agent_name: str,
    description: str,
    input_preview: str = "",
    expected_output: str = "",
    timeout: float = 3600,
) -> ApprovalDecision:
    """
    暂停执行并等待人工审核的便捷函数。
    
    用法:
        decision = await pause_for_approval(
            "定方向", "tangseng",
            "唐僧将分析客户需求并确定取经方向",
            input_preview=transcript[:500],
            expected_output="需求分析 + 取经路线建议"
        )
        if decision == APPROVE:
            # 继续执行
        elif decision == REJECT:
            # 返回重新处理
    """
    ha = HumanApproval()
    ha.require_approval_for(phase_name)
    return await ha.wait_for_approval(
        phase_name=phase_name,
        agent_name=agent_name,
        description=description,
        input_preview=input_preview,
        expected_output=expected_output,
        timeout=timeout,
    )
