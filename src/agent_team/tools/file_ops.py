"""File system tools for agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def read_file(path: str | Path) -> str:
    """Read a file from the workspace."""
    return Path(path).read_text()


def write_file(path: str | Path, content: str) -> None:
    """Write content to a file in the workspace."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def list_files(directory: str | Path, pattern: str = "*") -> list[str]:
    """List files in a directory matching a glob pattern."""
    return [str(p) for p in Path(directory).glob(pattern)]


def project_summary(workspace: str | Path) -> dict[str, Any]:
    """Generate a summary of the project workspace."""
    ws = Path(workspace)
    if not ws.exists():
        return {"error": f"Workspace not found: {workspace}"}
    
    files = {}
    for p in ws.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            files[str(p.relative_to(ws))] = p.stat().st_size
    
    return {
        "workspace": str(ws),
        "total_files": len(files),
        "files": files,
    }
