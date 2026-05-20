"""西游Control Plane — FastAPI server with WebSocket."""

from __future__ import annotations

import json
import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import get_control_plane

# Read the dashboard HTML
_DASHBOARD_PATH = Path(__file__).parent / "dashboard.html"


def create_app(config_dir: str | Path = "config") -> FastAPI:
    """Create the FastAPI control plane application."""
    app = FastAPI(title="西游Agent团队 · 控制面板", version="1.0.0")
    cp = get_control_plane(config_dir)

    # ── Dashboard ──────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        if _DASHBOARD_PATH.exists():
            return _DASHBOARD_PATH.read_text(encoding="utf-8")
        return "<h1>Dashboard not found</h1>"

    # ── API ────────────────────────────────────────────

    @app.get("/api/status")
    async def status():
        return cp.get_team_status()

    @app.get("/api/agents")
    async def agents():
        return cp.team.list_agents()

    @app.get("/api/workflows")
    async def workflows():
        return cp.team.list_workflows()

    @app.get("/api/events")
    async def events(since: int = 0):
        return cp.get_event_history(since)

    # ── Harness API ───────────────────────────────────

    @app.get("/api/harness/trace")
    async def harness_trace():
        """获取trace追踪树."""
        t = cp.team
        return {
            "summary": t.tracer.get_summary(),
            "tree": t.tracer.get_tree(),
        }

    @app.get("/api/harness/checkpoints")
    async def harness_checkpoints():
        """获取状态机检查点."""
        if cp.team._state_machine:
            return cp.team._state_machine.get_status_summary()
        return {"status": "no_state_machine"}

    @app.get("/api/harness/approvals")
    async def harness_approvals():
        """获取待审批列表."""
        pending = cp.team.approval.gate.pending()
        return [
            {
                "request_id": r.request_id,
                "phase": r.phase_name,
                "agent": r.agent_name,
                "description": r.description,
                "input_preview": r.input_preview[:300],
                "expected_output": r.expected_output,
                "timestamp": r.timestamp,
            }
            for r in pending
        ]

    @app.post("/api/harness/approve")
    async def harness_approve(data: dict):
        """审批通过."""
        request_id = data.get("request_id", "")
        note = data.get("note", "")
        try:
            cp.team.approval.gate.approve(request_id, note)
            return {"status": "approved"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @app.post("/api/harness/reject")
    async def harness_reject(data: dict):
        """审批驳回."""
        request_id = data.get("request_id", "")
        reason = data.get("reason", "")
        try:
            cp.team.approval.gate.reject(request_id, reason)
            return {"status": "rejected"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @app.post("/api/harness/recover")
    async def harness_recover():
        """从checkpoint恢复工作流."""
        t = cp.team
        if not t._workspace:
            return {"status": "error", "message": "No project"}
        from agent_team.harness.state_machine import WorkflowStateMachine
        sm = WorkflowStateMachine.load_from_checkpoint(t._workspace)
        if sm is None:
            return {"status": "error", "message": "No checkpoint found"}
        return {
            "status": "ok",
            "workflow_id": sm.workflow_id,
            "completed": len(sm.completed_phases),
            "total": len(sm.phases),
            "can_resume": True,
        }

    @app.get("/api/harness/guardrail_log")
    async def harness_guardrail_log():
        """获取guardrail校验日志."""
        # Guardrail events are embedded in the event stream
        guardrail_events = [
            e for e in cp._events
            if isinstance(e, dict) and e.get("event_type") == "guardrail_warning"
        ]
        return guardrail_events[-20:]

    @app.post("/api/project/init")
    async def init_project(data: dict):
        name = data.get("name", "default")
        transcript = data.get("transcript", "")
        ws = cp.team.init_project(name, transcript)
        return {"status": "ok", "workspace": str(ws)}

    @app.post("/api/workflow/start")
    async def start_workflow(data: dict):
        wf = data.get("workflow", "qujing")
        result = await cp.start_workflow(wf)
        return result

    @app.post("/api/chat")
    async def chat_with_tangseng(data: dict):
        message = data.get("message", "")
        if not message:
            return {"error": "No message"}
        response = await cp.team.chat_with_tangseng(message)
        return {"response": response}

    @app.post("/api/analyze")
    async def analyze_transcript(data: dict):
        transcript = data.get("transcript", "")
        if not transcript:
            return {"error": "No transcript"}
        response = await cp.team.tangseng_analyze(transcript)
        return {"response": response}

    @app.get("/api/project/documents")
    async def project_documents():
        t = cp.team
        if not t._workspace:
            return []
        docs = []
        for p in t._workspace.glob("docs/**/*.md"):
            docs.append({
                "path": str(p.relative_to(t._workspace)),
                "content": p.read_text()[:2000] if p.exists() else "",
            })
        return docs

    @app.post("/api/events/clear")
    async def clear_events():
        cp.clear_events()
        return {"status": "ok"}

    # ── WebSocket ──────────────────────────────────────

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        cp.subscribe(ws)
        try:
            # Send current status on connect
            await ws.send_text(json.dumps({
                "type": "connected",
                "status": cp.get_team_status(),
            }, ensure_ascii=False))
            
            # Keep connection alive and handle client messages
            while True:
                data = await ws.receive_text()
                msg = json.loads(data)
                cmd = msg.get("command", "")
                
                if cmd == "start_workflow":
                    await cp.start_workflow(msg.get("workflow", "qujing"))
                elif cmd == "chat":
                    response = await cp.team.chat_with_tangseng(msg.get("message", ""))
                    await ws.send_text(json.dumps({
                        "type": "chat_response",
                        "response": response,
                    }, ensure_ascii=False))
                elif cmd == "init_project":
                    cp.team.init_project(msg.get("name", ""), msg.get("transcript", ""))
                    await ws.send_text(json.dumps({
                        "type": "status_update",
                        "status": cp.get_team_status(),
                    }, ensure_ascii=False))
                elif cmd == "analyze":
                    transcript = msg.get("transcript", "")
                    if transcript:
                        await cp.team.tangseng_analyze(transcript)
                elif cmd == "get_status":
                    await ws.send_text(json.dumps({
                        "type": "status_update",
                        "status": cp.get_team_status(),
                    }, ensure_ascii=False))
                    
        except WebSocketDisconnect:
            cp.unsubscribe(ws)
        except Exception as e:
            cp.unsubscribe(ws)
            logger.error(f"WebSocket error: {e}")

    return app


def main():
    """Entry point for running the control plane."""
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8866, log_level="info")


if __name__ == "__main__":
    main()
