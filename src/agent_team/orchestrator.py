"""西游Agent团队 · 编排引擎 — TangSeng coordinates four disciples.

集成了Harness工程保障层:
- Guardrails: 输入/输出/工具调用校验
- Tracing: Span-based可追踪调用链
- Handoffs: Agent间交接过滤
- State Machine: 可恢复可重放状态机
- Human-in-the-loop: 审核/暂停/恢复
"""

from __future__ import annotations

import asyncio
import logging
import re
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from .agents import AgentConfig, BaseAgent, Task
from .agents.agents import BajieAgent, WuKongAgent, ShaSengAgent, BaiLongMaAgent
from .llm import get_provider, LLMProvider

# Harness imports
from .harness.guardrails import (
    InputGuardrail, OutputGuardrail, ToolGuardrail,
    PIIGuardrail, CompositeGuardrail, GuardrailResult,
)
from .harness.tracing import Tracer, get_tracer, reset_tracer
from .harness.handoffs import handoff_registry, AgentHandoff
from .harness.state_machine import (
    WorkflowStateMachine, PhaseStatus, WorkflowStatus, Checkpoint,
)
from .harness.human_loop import HumanApproval, ApprovalGate, ApprovalDecision
from .harness.contract import ContractVerifier, CoverageReport, Requirement

logger = logging.getLogger(__name__)


# ── Event System for Control Plane ──────────────────────

@dataclass
class AgentEvent:
    """Real-time event emitted during workflow execution."""
    event_id: str
    event_type: str       # phase_start, phase_end, delegation, agent_output, workflow_start, workflow_end, tangseng_thought
    agent_name: str       # tangseng, bajie, wukong, shaseng, bailongma
    agent_emoji: str
    phase_name: str
    message: str
    data: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_json(self) -> str:
        return json.dumps({
            "event_id": self.event_id,
            "event_type": self.event_type,
            "agent_name": self.agent_name,
            "agent_emoji": self.agent_emoji,
            "phase_name": self.phase_name,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp,
        }, ensure_ascii=False)


@dataclass
class PhaseResult:
    phase_name: str
    agent_name: str
    action: str
    output: str
    status: str
    started_at: str = ""
    finished_at: str = ""


@dataclass
class WorkflowRun:
    workflow_name: str
    workspace: Path
    phases: list[PhaseResult] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""


class AgentTeam:
    """西游Agent团队 — TangSeng + four disciples."""

    AGENT_NAMES = ["tangseng", "bajie", "wukong", "shaseng", "bailongma"]

    def __init__(
        self,
        config_path: str | Path = "config/agents.yaml",
        workflows_path: str | Path = "config/workflows.yaml",
        base_workspace: str | Path = "workspaces",
    ):
        self.config_path = Path(config_path)
        self.workflows_path = Path(workflows_path)
        self.base_workspace = Path(base_workspace)

        self._config = yaml.safe_load(self.config_path.read_text())
        self._workflows = yaml.safe_load(self.workflows_path.read_text())

        self._agent_configs: dict[str, AgentConfig] = {}
        self._load_agent_configs()

        self._agents: dict[str, BaseAgent] = {}
        self._workspace: Path | None = None
        self._project_name: str | None = None
        self._transcript: str | None = None
        self._project_brief: str = ""  # 从对话分析中提取的项目概述
        self._tangseng_conversation: list[dict[str, str]] = []

        # Event subscribers for control plane
        self._event_subscribers: list[Callable[[AgentEvent], None]] = []
        self._event_counter = 0
        
        # ── Harness Engineering Layer ──────────────────
        # Guardrails: 输入/输出校验
        self.input_guardrail = CompositeGuardrail([
            InputGuardrail(max_length=50000, max_tokens_estimate=16000),
            PIIGuardrail(block_on_pii=False),
        ], mode="soft")  # soft mode: 记录但不拦截
        
        self.output_guardrail = OutputGuardrail(
            min_length=10, required_format=None
        )
        
        self.tool_guardrail = ToolGuardrail(
            timeout_seconds=30, max_retries=3, retry_delay=1.0
        )
        
        # Tracing: span-based调用追踪
        self.tracer: Tracer = get_tracer()
        
        # Handoffs: Agent间交接过滤
        self.handoff = handoff_registry
        
        # State Machine: 可恢复工作流 (lazy init per workflow)
        self._state_machine: Optional[WorkflowStateMachine] = None
        
        # Human-in-the-loop: 审核门（CLI默认自动通过，控制面板可启用）
        self.approval = HumanApproval()
        # self.approval.require_approval_for("定方向")  # 如需审核取消注释
        
        self._harness_enabled = True
        self._auto_approve = True     # 默认自动通过审核
        
        # Contract verification (lazy init)
        self._contract: Optional[ContractVerifier] = None

    # ── Event System ────────────────────────────────────

    def on_event(self, callback: Callable[[AgentEvent], None]):
        """Subscribe to agent events (for control plane WebSocket)."""
        self._event_subscribers.append(callback)

    def _emit(self, event_type: str, agent_name: str, phase_name: str,
              message: str, data: dict | None = None):
        """Emit an event to all subscribers."""
        self._event_counter += 1
        cfg = self._agent_configs.get(agent_name)
        emoji = cfg.emoji if cfg and hasattr(cfg, 'emoji') else "🤖"
        
        # Resolve emoji from config
        if agent_name in self._agent_configs:
            raw_cfg = self._config[agent_name]
            emoji = raw_cfg.get("emoji", "🤖")
        
        event = AgentEvent(
            event_id=f"evt_{self._event_counter:04d}",
            event_type=event_type,
            agent_name=agent_name,
            agent_emoji=emoji,
            phase_name=phase_name,
            message=message,
            data=data or {},
        )
        for sub in self._event_subscribers:
            try:
                sub(event)
            except Exception as e:
                logger.error(f"Event subscriber error: {e}")

    # ── Config ──────────────────────────────────────────

    def _load_agent_configs(self):
        for agent_name in self.AGENT_NAMES:
            cfg = self._config[agent_name]
            self._agent_configs[agent_name] = AgentConfig(
                name=cfg["name"],
                role=cfg["role"],
                model=cfg["model"],
                provider=cfg["provider"],
                temperature=cfg.get("temperature", 0.4),
                max_tokens=cfg.get("max_tokens", 4096),
                system_prompt=cfg.get("system_prompt", ""),
                description=cfg.get("description", ""),
            )
            # Store extra fields
            self._agent_configs[agent_name].emoji = cfg.get("emoji", "🤖")
            self._agent_configs[agent_name].color = cfg.get("color", "#888")
            self._agent_configs[agent_name].personality = cfg.get("personality", "")

    def _get_agent(self, name: str) -> BaseAgent:
        if name not in self._agents:
            cfg = self._agent_configs[name]
            llm = get_provider(cfg.provider)
            
            # Inject client context into system prompt
            system_prompt = cfg.system_prompt
            if self._project_name:
                system_prompt = system_prompt.replace("{client_name}", self._project_name)
                system_prompt = system_prompt.replace("{project_brief}", self._project_brief or "待分析")
                system_prompt = system_prompt.replace("{workspace}", str(self.workspace) if self._workspace else "")
            cfg.system_prompt = system_prompt
            
            # Create tool registry for agents that need tools
            tool_registry = None
            if name in ("wukong", "shaseng", "bailongma") and self._workspace:
                from .tools.registry import ToolRegistry
                tool_registry = ToolRegistry(self.workspace)
            
            if name == "bajie":
                self._agents[name] = BajieAgent(cfg, llm, tool_registry)
            elif name == "wukong":
                self._agents[name] = WuKongAgent(cfg, llm, tool_registry)
            elif name == "shaseng":
                self._agents[name] = ShaSengAgent(cfg, llm, tool_registry)
            elif name == "bailongma":
                self._agents[name] = BaiLongMaAgent(cfg, llm, tool_registry)
            else:
                self._agents[name] = BaseAgent(cfg, llm, tool_registry)
        return self._agents[name]

    @property
    def tangseng(self) -> BaseAgent:
        return self._get_agent("tangseng")

    @property
    def workspace(self) -> Path:
        if self._workspace is None:
            raise RuntimeError("No project. Call init_project() first.")
        return self._workspace

    @property
    def agent_configs(self) -> dict[str, AgentConfig]:
        return self._agent_configs

    # ── Project Lifecycle ───────────────────────────────

    def init_project(self, project_name: str, transcript: str = "") -> Path:
        self._project_name = project_name
        self._workspace = self.base_workspace / project_name
        self._workspace.mkdir(parents=True, exist_ok=True)
        
        # Auto-load existing transcript from workspace
        if not transcript:
            transcript_path = self._workspace / "transcript.txt"
            if transcript_path.exists():
                transcript = transcript_path.read_text()
        
        self._transcript = transcript

        (self._workspace / "docs" / "client").mkdir(parents=True, exist_ok=True)
        (self._workspace / "src").mkdir(exist_ok=True)
        (self._workspace / "tests").mkdir(exist_ok=True)

        if transcript:
            (self._workspace / "transcript.txt").write_text(transcript)
            # Auto-extract project brief: first 200 chars of transcript as summary
            self._project_brief = transcript.strip()[:200]
            if len(transcript.strip()) > 200:
                self._project_brief += "..."

        meta = {
            "project_name": project_name,
            "created_at": datetime.now().isoformat(),
            "status": "active",
        }
        (self._workspace / "project.yaml").write_text(yaml.dump(meta))

        self._emit("project_init", "tangseng", "", f"新项目「{project_name}」已创建，准备取经！", 
                   {"project": project_name})
        return self._workspace

    # ── 唐僧对话 ────────────────────────────────────────

    def _build_tangseng_context(self) -> str:
        parts = []
        if self._project_name:
            parts.append(f"📁 项目: {self._project_name}")
        if self._transcript:
            t = self._transcript
            if len(t) > 4000:
                t = t[:4000] + "\n...[省略]"
            parts.append(f"📋 客户对话:\n{t}")
        if self._workspace and self._workspace.exists():
            docs = list(self._workspace.glob("docs/**/*.md"))
            if docs:
                parts.append("📄 已有文档:")
                for d in docs:
                    parts.append(f"  - {d.relative_to(self._workspace)}")
        return "\n\n".join(parts) if parts else "暂无项目上下文。"

    async def chat_with_tangseng(self, message: str) -> str:
        context = self._build_tangseng_context()
        full = f"{context}\n\n---\n师父: {message}"
        self._tangseng_conversation.append({"role": "user", "content": full})
        response = await self.tangseng.achat(full)
        self._tangseng_conversation.append({"role": "assistant", "content": response})
        self._emit("tangseng_thought", "tangseng", "", response[:200],
                   {"full_response": response})
        return response

    def chat_with_tangseng_sync(self, message: str) -> str:
        context = self._build_tangseng_context()
        full = f"{context}\n\n---\n师父: {message}"
        self._tangseng_conversation.append({"role": "user", "content": full})
        response = self.tangseng.chat(full)
        self._tangseng_conversation.append({"role": "assistant", "content": response})
        self._emit("tangseng_thought", "tangseng", "", response[:200])
        return response

    async def tangseng_analyze(self, transcript: str) -> str:
        self._transcript = transcript
        # Save transcript to workspace
        if self._workspace:
            (self._workspace / "transcript.txt").write_text(transcript)
        context = self._build_tangseng_context()
        prompt = (
            f"{context}\n\n"
            "请分析这段客户对话：\n"
            "1. 客户的业务和痛点\n"
            "2. 表面需求 vs 真正需求\n"
            "3. 需要跟师父确认的问题\n"
            "4. 取经路线建议（范围和方法）\n"
        )
        return await self.chat_with_tangseng(prompt)

    # ── Workflow Execution ──────────────────────────────

    async def run_workflow(self, workflow_name: str = "qujing",
                           use_state_machine: bool = True) -> WorkflowRun:
        """
        执行工作流。
        
        Args:
            workflow_name: qujing / tanlu / xiance
            use_state_machine: 是否使用可恢复状态机(默认True)
        """
        if workflow_name not in self._workflows["workflows"]:
            available = list(self._workflows["workflows"].keys())
            raise ValueError(f"未知工作流 '{workflow_name}'。可选: {available}")

        wf_def = self._workflows["workflows"][workflow_name]
        run = WorkflowRun(
            workflow_name=workflow_name,
            workspace=self.workspace,
            started_at=datetime.now().isoformat(),
        )

        self._emit("workflow_start", "tangseng", workflow_name,
                   f"🎬 开始工作流: {workflow_name}",
                   {"workflow": workflow_name, "phases": len(wf_def["phases"])})

        # ── Harness: Init State Machine ────────────────
        if use_state_machine and self._harness_enabled:
            self._state_machine = WorkflowStateMachine(
                workflow_name=workflow_name,
                phases=wf_def["phases"],
                workspace=self.workspace,
            )
            # 注册需要审核的phase
            for phase_name in self.approval._required_phases:
                if phase_name in self._state_machine.phases:
                    self._state_machine.require_approval(phase_name)

        # ── Execute with State Machine ──────────────────
        if use_state_machine and self._harness_enabled and self._state_machine:
            sm = self._state_machine
            
            async def execute_fn(phase_name: str, agent_name: str, ctx: dict):
                """状态机回调: 执行单个phase."""
                phase_def = next((p for p in wf_def["phases"] if p["name"] == phase_name), None)
                if phase_def is None:
                    return "", False
                
                action = phase_def.get("action", "execute")
                description = phase_def.get("description", "")
                
                # Check human-in-the-loop
                if self.approval.needs_approval(phase_name) and not self._auto_approve:
                    self._emit("awaiting_approval", agent_name, phase_name,
                               f"⏸️ {phase_name} 等待师父审核...")
                    decision = await self.approval.wait_for_approval(
                        phase_name=phase_name,
                        workflow_id=sm.workflow_id,
                        agent_name=agent_name,
                        description=description,
                        timeout=300,  # 5分钟超时自动跳过
                    )
                    if decision == ApprovalDecision.REJECT:
                        return "人工审核驳回", False
                    elif decision == ApprovalDecision.SKIP:
                        return "", True  # 跳过但标记成功
                
                # Execute
                self._emit("phase_start", agent_name, phase_name,
                           f"▶️ {description}",
                           {"agent": agent_name, "phase": phase_name, "action": action})
                
                if agent_name == "tangseng":
                    result = await self._run_tangseng_phase(phase_name, action, description)
                    # ── Contract: Extract requirements after analysis ──
                    if phase_name == "定方向" and result.status == "done" and self._harness_enabled:
                        self._contract = ContractVerifier(self.workspace)
                        reqs = self._contract.extract_requirements(
                            transcript=self._transcript or "",
                            tangseng_analysis=result.output,
                            llm_call=lambda p: self.tangseng.chat(p)
                        )
                        self._emit("contract", "system", phase_name,
                                   f"📋 提取了 {len(reqs)} 条需求",
                                   {"requirement_count": len(reqs)})
                elif agent_name == "bajie":
                    result = await self._run_disciple_phase(agent_name, phase_name, action, description)
                    # ── Contract: Verify PRD coverage ──
                    if phase_name == "出主意" and result.status == "done" and self._contract:
                        prd_path = self.workspace / "docs" / "PRD.md"
                        if prd_path.exists():
                            rpt = self._contract.verify_prd_coverage(prd_path.read_text())
                            gap_list = [r.description[:80] for r in rpt.uncovered]
                            self._emit("contract", "system", phase_name,
                                       f"{'✅' if rpt.passed else '❌'} PRD覆盖率: {rpt.coverage_pct:.0f}% ({rpt.covered}/{rpt.total_requirements})",
                                       {"coverage": rpt.coverage_pct, "passed": rpt.passed, "gaps": gap_list})
                elif agent_name == "wukong":
                    result = await self._run_disciple_phase(agent_name, phase_name, action, description)
                    # ── Contract: Verify code coverage ──
                    if phase_name == "打头阵" and result.status == "done" and self._contract:
                        rpt = self._contract.verify_code_coverage()
                        gap_list = [r.description[:80] for r in rpt.uncovered]
                        self._emit("contract", "system", phase_name,
                                   f"{'✅' if rpt.passed else '❌'} 代码覆盖率: {rpt.coverage_pct:.0f}% ({rpt.covered}/{rpt.total_requirements})",
                                   {"coverage": rpt.coverage_pct, "passed": rpt.passed, "gaps": gap_list})
                        # ── Auto-fix: if PRD gap exists, re-task 八戒 ──
                        if not rpt.passed and gap_list:
                            fix_task = "⚠️ 需求契约验证发现以下客户需求未在PRD中覆盖:\n" + \
                                "\n".join(f"  - {g}" for g in gap_list) + \
                                "\n\n请更新 docs/PRD.md，补充这些缺失的功能需求。"
                            self._emit("contract_action", "system", phase_name,
                                       f"🔧 自动触发: 八戒重新补充PRD ({len(gap_list)}项缺失)")
                            fix_result = await self._run_disciple_phase("bajie", "补PRD", "update_prd", fix_task)
                            if fix_result.status == "done":
                                rpt2 = self._contract.verify_prd_coverage(
                                    (self.workspace / "docs" / "PRD.md").read_text()
                                )
                                self._emit("contract", "system", "补PRD",
                                           f"{'✅' if rpt2.passed else '⚠️'} 补充后PRD覆盖率: {rpt2.coverage_pct:.0f}%")
                                # Re-run 悟空 with updated PRD
                                if rpt2.passed:
                                    self._emit("contract_action", "system", phase_name,
                                               "🔧 自动触发: 悟空根据更新后的PRD重新开发")
                                    rerun_result = await self._run_disciple_phase("wukong", "补开发", "implement",
                                        "根据更新后的PRD重新开发。特别关注: 订单录入、LINE Bot对接、厨房通知。")
                                    if rerun_result.status == "done":
                                        self._contract.verify_code_coverage()
                else:
                    result = await self._run_disciple_phase(agent_name, phase_name, action, description)
                
                if result.status == "done":
                    self._emit("phase_end", agent_name, phase_name,
                               f"✅ {phase_name} 完成",
                               {"output_preview": result.output[:300]})
                    return result.output, True
                else:
                    error_msg = result.output[:200] if result.output else "未知错误"
                    self._emit("phase_end", agent_name, phase_name,
                               f"❌ {phase_name} 失败: {error_msg}",
                               {"error": error_msg})
                    logger.error(f"Phase '{phase_name}' 失败: {error_msg}")
                    return result.output, False
            
            # Run state machine
            sm_result = await sm.resume(execute_fn)
            
            # Convert state machine results to WorkflowRun
            for phase_name in sm._phase_order:
                ps = sm.phases[phase_name]
                status = "done" if ps.status in (PhaseStatus.COMPLETED, PhaseStatus.FALLBACK) else \
                         "failed" if ps.status == PhaseStatus.FAILED else \
                         "skipped" if ps.status == PhaseStatus.SKIPPED else "pending"
                
                run.phases.append(PhaseResult(
                    phase_name=phase_name,
                    agent_name=ps.agent_name,
                    action="",
                    output=ps.output,
                    status=status,
                    started_at=ps.started_at,
                    finished_at=ps.finished_at,
                ))
            
            # ── Harness: Export trace ──────────────────
            if self._harness_enabled:
                trace_path = self.workspace / "trace.json"
                self.tracer.export_json(trace_path)
                self._emit("trace_exported", "system", "",
                           f"📊 追踪数据已导出: {trace_path}",
                           {"trace_summary": self.tracer.get_summary()})
        
        else:
            # ── Legacy execution (无状态机) ────────────
            completed: set[str] = set()
            for phase in wf_def["phases"]:
                phase_name = phase["name"]
                agent_name = phase["agent"]
                action = phase.get("action", "execute")
                description = phase.get("description", "")
                depends_on = phase.get("depends_on", [])
                optional = phase.get("optional", False)

                if depends_on and not all(dep in completed for dep in depends_on):
                    if optional:
                        self._emit("phase_skip", agent_name, phase_name,
                                   f"⏭️ {phase_name} 跳过（依赖未满足）")
                        run.phases.append(PhaseResult(
                            phase_name=phase_name, agent_name=agent_name,
                            action=action, output="", status="skipped",
                        ))
                        continue
                    else:
                        raise RuntimeError(f"阶段 '{phase_name}' 依赖 {depends_on}未完成")

                self._emit("phase_start", agent_name, phase_name,
                           f"▶️ {description}",
                           {"agent": agent_name, "phase": phase_name, "action": action})

                if agent_name == "tangseng":
                    result = await self._run_tangseng_phase(phase_name, action, description)
                else:
                    result = await self._run_disciple_phase(agent_name, phase_name, action, description)

                run.phases.append(result)
                if result.status == "done":
                    completed.add(phase_name)
                    self._emit("phase_end", agent_name, phase_name,
                               f"✅ {phase_name} 完成",
                               {"output_preview": result.output[:300]})
                elif not optional:
                    self._emit("phase_end", agent_name, phase_name,
                               f"❌ {phase_name} 失败", {"error": result.output[:300]})
                    break

        run.finished_at = datetime.now().isoformat()

        self._emit("workflow_end", "tangseng", workflow_name,
                   f"🏁 工作流完成: {workflow_name}",
                   {"total": len(run.phases),
                    "done": sum(1 for p in run.phases if p.status == "done"),
                    "failed": sum(1 for p in run.phases if p.status == "failed")})

        # Save log
        log_path = self.workspace / "workflow_log.yaml"
        log_path.write_text(yaml.dump({
            "workflow": workflow_name,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "phases": [{"name": p.phase_name, "agent": p.agent_name, "status": p.status}
                       for p in run.phases],
        }))

        return run

    async def _run_tangseng_phase(self, phase_name: str, action: str, description: str) -> PhaseResult:
        started = datetime.now().isoformat()
        self._emit("agent_think", "tangseng", phase_name, f"🤔 唐僧思考中: {description}")

        try:
            if action == "analyze_transcript":
                if not self._transcript:
                    return PhaseResult(phase_name=phase_name, agent_name="tangseng",
                                       action=action, output="没有对话记录", status="failed")
                output = await self.chat_with_tangseng(
                    f"阶段: {phase_name} — {description}\n\n"
                    "分析客户对话，给出：1)客户摘要 2)核心需求 3)建议范围 4)委派任务(用@bajie/@wukong等格式)"
                )
            elif action == "review_and_deliver":
                output = await self.chat_with_tangseng(
                    f"阶段: {phase_name} — {description}\n\n"
                    "审核所有徒弟的产出，准备最终交付。确认所有内容一致、完整、可交付给客户。"
                )
            else:
                output = await self.chat_with_tangseng(f"阶段: {phase_name} — {description}")

            return PhaseResult(phase_name=phase_name, agent_name="tangseng",
                               action=action, output=output, status="done",
                               started_at=started, finished_at=datetime.now().isoformat())
        except Exception as e:
            logger.error(f"唐僧阶段 '{phase_name}' 异常: {e}")
            return PhaseResult(phase_name=phase_name, agent_name="tangseng",
                               action=action, output=f"ERROR: {e}", status="failed",
                               started_at=started, finished_at=datetime.now().isoformat())

    async def _run_disciple_phase(self, agent_name: str, phase_name: str,
                                   action: str, description: str) -> PhaseResult:
        """执行徒弟phase — 带Harness保障层."""
        started = datetime.now().isoformat()
        agent = self._get_agent(agent_name)
        cfg = self._agent_configs[agent_name]

        self._emit("agent_think", agent_name, phase_name,
                   f"{cfg.emoji} {cfg.name}工作中: {description}")

        task = Task(
            task_id=f"{phase_name}_{int(datetime.now().timestamp())}",
            agent_name=agent_name,
            description=f"阶段: {phase_name}\n动作: {action}\n\n{description}",
        )

        try:
            # ── Harness: Input Guardrail ──────────────
            if self._harness_enabled:
                gr_result = await self.input_guardrail.check(
                    task.description,
                    context={"phase": phase_name, "agent": agent_name}
                )
                if not gr_result.passed:
                    self._emit("guardrail_warning", agent_name, phase_name,
                               f"⚠️ 输入校验警告: {gr_result.message}",
                               {"guardrail": "input", "result": gr_result.message})
            
            # ── Harness: Tracing span ──────────────────
            span_id = ""
            if self._harness_enabled:
                span = self.tracer.start_span(
                    agent_name, phase_name, "execute",
                    tags=["harness", f"agent:{agent_name}", f"phase:{phase_name}"]
                )
                span.input_preview = task.description[:500]
                span_id = span.span_id
            
            # ── Execute Agent ──────────────────────────
            output = await agent.execute(task, self.workspace)
            
            # ── Harness: Output Guardrail ──────────────
            if self._harness_enabled:
                gr_result = await self.output_guardrail.check(
                    output,
                    context={"phase": phase_name, "agent": agent_name}
                )
                if gr_result.passed:
                    self.tracer.add_guardrail_check(span_id, {
                        "type": "output", "passed": True, "message": gr_result.message
                    })
                else:
                    self._emit("guardrail_warning", agent_name, phase_name,
                               f"⚠️ 输出校验警告: {gr_result.message}",
                               {"guardrail": "output", "result": gr_result.message})
                    self.tracer.add_guardrail_check(span_id, {
                        "type": "output", "passed": False, "message": gr_result.message
                    })
            
            # ── Harness: End tracing span ──────────────
            if self._harness_enabled and span_id:
                span = self.tracer.get_span(span_id)
                if span:
                    span.output_preview = output[:500]
                self.tracer.end_span(span_id, "success")
            
            # ── Harness: Record handoff ────────────────
            # Record the output for potential handoff filtering
            if self._harness_enabled:
                self._last_agent_output = output
            
            self._emit("agent_output", agent_name, phase_name,
                       output[:300] + ("..." if len(output) > 300 else ""),
                       {"full_output": output, "preview": output[:500]})
            status = "done"
            
        except Exception as e:
            logger.error(f"{agent_name} 失败: {e}")
            output = f"ERROR: {e}"
            status = "failed"
            
            # ── Harness: Mark span as error ────────────
            if self._harness_enabled and span_id:
                self.tracer.end_span(span_id, "error", str(e))
            
            self._emit("agent_output", agent_name, phase_name,
                       f"❌ 失败: {e}", {"error": str(e)})

        return PhaseResult(phase_name=phase_name, agent_name=agent_name,
                           action=action, output=output, status=status,
                           started_at=started, finished_at=datetime.now().isoformat())

    # ── Delegation Parsing ──────────────────────────────

    def parse_delegations(self, tangseng_output: str) -> list[Task]:
        tasks: list[Task] = []
        pattern = r'@(\w+):\s*(.+?)(?=\n@|\Z)'
        for i, (agent, desc) in enumerate(re.findall(pattern, tangseng_output, re.DOTALL)):
            agent = agent.lower()
            if agent in ["bajie", "wukong", "shaseng", "bailongma"]:
                tasks.append(Task(
                    task_id=f"deleg_{i}_{int(datetime.now().timestamp())}",
                    agent_name=agent,
                    description=desc.strip(),
                ))
                self._emit("delegation", "tangseng", "",
                           f"📋 委派 → @{agent}: {desc.strip()[:100]}",
                           {"from": "tangseng", "to": agent, "task": desc.strip()[:200]})
        return tasks

    async def delegate_and_collect(self, tangseng_output: str) -> dict[str, str]:
        tasks = self.parse_delegations(tangseng_output)
        if not tasks:
            return {}

        async def run_task(task: Task) -> tuple[str, str]:
            agent = self._get_agent(task.agent_name)
            try:
                output = await agent.execute(task, self.workspace)
                return task.agent_name, output
            except Exception as e:
                return task.agent_name, f"ERROR: {e}"

        results = await asyncio.gather(*[run_task(t) for t in tasks])
        return dict(results)

    # ── Utilities ───────────────────────────────────────

    def list_agents(self) -> list[dict]:
        return [
            {
                "key": name,
                "name": cfg.name,
                "emoji": self._config[name].get("emoji", "🤖"),
                "role": cfg.role,
                "model": cfg.model,
                "provider": cfg.provider,
                "color": self._config[name].get("color", "#888"),
                "personality": self._config[name].get("personality", ""),
                "description": cfg.description,
            }
            for name, cfg in self._agent_configs.items()
        ]

    def list_workflows(self) -> list[dict]:
        return [
            {"name": name, "description": wf["description"]}
            for name, wf in self._workflows["workflows"].items()
        ]

    def get_status(self) -> dict:
        return {
            "project": self._project_name,
            "workspace": str(self._workspace) if self._workspace else None,
            "has_transcript": bool(self._transcript),
            "documents": [
                str(p.relative_to(self._workspace))
                for p in self.workspace.glob("docs/**/*.md")
            ] if self._workspace and self._workspace.exists() else [],
        }
