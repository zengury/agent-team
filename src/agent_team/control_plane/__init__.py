"""西游Control Plane — 实时控制面板服务器."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


class ControlPlaneServer:
    """
    Control plane that wires together:
    - AgentTeam orchestration
    - WebSocket event broadcasting
    - HTTP API for control
    
    This is designed to be embedded in a FastAPI app.
    """

    def __init__(self, config_dir: str | Path = "config"):
        self.config_dir = Path(config_dir)
        self._subscribers: list = []  # WebSocket connections
        self._events: list[dict] = []  # Event history
        self._team = None  # Lazy init to avoid import issues
        self._workflow_task: Optional[asyncio.Task] = None

    @property
    def team(self):
        if self._team is None:
            from ..orchestrator import AgentTeam
            self._team = AgentTeam(
                config_path=str(self.config_dir / "agents.yaml"),
                workflows_path=str(self.config_dir / "workflows.yaml"),
            )
            # Wire events to all subscribers
            self._team.on_event(self._broadcast_event)
        return self._team

    def _broadcast_event(self, event):
        """Send event to all WebSocket subscribers."""
        data = event.to_json() if hasattr(event, 'to_json') else json.dumps(event, ensure_ascii=False)
        self._events.append(json.loads(data) if isinstance(data, str) else event)
        # Keep last 500 events
        if len(self._events) > 500:
            self._events = self._events[-500:]
        
        # Broadcast to WebSocket clients
        dead = []
        for ws in self._subscribers:
            try:
                asyncio.create_task(ws.send_text(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._subscribers.remove(ws)

    def subscribe(self, websocket):
        """Add a WebSocket subscriber."""
        self._subscribers.append(websocket)

    def unsubscribe(self, websocket):
        """Remove a WebSocket subscriber."""
        if websocket in self._subscribers:
            self._subscribers.remove(websocket)

    def get_team_status(self) -> dict:
        """Full team status for the dashboard."""
        t = self.team
        # Auto-detect project if not initialized
        if not t._workspace:
            workspaces_dir = t.base_workspace
            if workspaces_dir.exists():
                existing = sorted(workspaces_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
                if existing:
                    latest = existing[0]
                    if latest.is_dir() and (latest / "project.yaml").exists():
                        t.init_project(latest.name)
        
        return {
            "agents": t.list_agents(),
            "workflows": t.list_workflows(),
            "project": t.get_status(),
            "events": self._events[-50:],  # Last 50 events
            "config": {
                "agents": {
                    name: {
                        "emoji": t._config[name].get("emoji", "🤖"),
                        "color": t._config[name].get("color", "#888"),
                        "role": t._config[name].get("role", ""),
                        "personality": t._config[name].get("personality", ""),
                        "model": t._config[name].get("model", ""),
                    }
                    for name in t.AGENT_NAMES
                }
            }
        }

    async def start_workflow(self, workflow_name: str = "qujing") -> dict:
        """Start a workflow and return initial status."""
        t = self.team
        if not t._workspace:
            return {"error": "No project. Init first."}
        
        # Run workflow in background
        async def _run():
            try:
                await t.run_workflow(workflow_name)
            except Exception as e:
                logger.error(f"Workflow error: {e}")
        
        self._workflow_task = asyncio.create_task(_run())
        return {"status": "started", "workflow": workflow_name}

    def get_event_history(self, since: int = 0) -> list[dict]:
        """Get events since a given index."""
        return self._events[since:]

    def clear_events(self):
        """Clear event history."""
        self._events = []


# ── Global singleton for FastAPI dependency injection ──
_control_plane: Optional[ControlPlaneServer] = None


def get_control_plane(config_dir: str | Path = "config") -> ControlPlaneServer:
    global _control_plane
    if _control_plane is None:
        _control_plane = ControlPlaneServer(config_dir)
    return _control_plane
