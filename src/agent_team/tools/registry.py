"""工具注册表 — Agent可调用的真实工具。

参考: OpenAI function calling / MCP tool pattern.

每种工具定义包含:
- name: 工具名称
- description: 描述(给LLM看)
- parameters: JSON Schema参数定义
- handler: 实际执行函数
"""

from __future__ import annotations

import json
import logging
import subprocess
import asyncio
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# OpenAI function calling JSON schema for a tool
ToolDef = dict[str, Any]  # {"type": "function", "function": {"name":..., "description":..., "parameters":...}}


class ToolRegistry:
    """工具注册表 — 管理Agent可用的工具集."""

    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace)
        self._tools: dict[str, dict] = {}  # name → {def, handler}
        self._register_defaults()

    def _register_defaults(self):
        """注册默认工具集."""
        self.register(
            name="read_file",
            description="读取工作区中的文件内容",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对于工作区的文件路径，如 'docs/PRD.md' 或 'src/main.py'"},
                },
                "required": ["path"],
            },
            handler=self._read_file,
        )
        self.register(
            name="write_file",
            description="写入内容到工作区文件。会创建必要的目录",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对于工作区的文件路径，如 'src/app.py'"},
                    "content": {"type": "string", "description": "要写入的完整文件内容"},
                },
                "required": ["path", "content"],
            },
            handler=self._write_file,
        )
        self.register(
            name="list_dir",
            description="列出工作区目录中的文件和子目录",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对于工作区的目录路径，如 'src' 或 '.'"},
                },
                "required": ["path"],
            },
            handler=self._list_dir,
        )
        self.register(
            name="run_shell",
            description="在工作区中执行shell命令。只能用于构建、测试、安装依赖等安全操作",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的shell命令"},
                },
                "required": ["command"],
            },
            handler=self._run_shell,
        )

    def register(self, name: str, description: str, parameters: dict, handler: Callable):
        """注册一个工具."""
        self._tools[name] = {
            "def": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
            "handler": handler,
        }

    @property
    def tool_schemas(self) -> list[dict]:
        """返回所有工具的OpenAI function calling格式定义."""
        return [t["def"] for t in self._tools.values()]

    async def execute(self, name: str, arguments: dict) -> str:
        """执行工具调用，返回结果字符串."""
        if name not in self._tools:
            return f"错误: 未知工具 '{name}'"
        
        handler = self._tools[name]["handler"]
        try:
            result = handler(**arguments)
            if asyncio.iscoroutine(result):
                result = await result
            return str(result)
        except Exception as e:
            logger.error(f"工具 {name} 执行失败: {e}")
            return f"工具执行错误: {e}"

    # ── 默认工具实现 ──────────────────────────────────

    def _resolve_path(self, path: str) -> Path:
        """解析路径，确保在工作区内."""
        resolved = (self.workspace / path).resolve()
        if not str(resolved).startswith(str(self.workspace.resolve())):
            raise ValueError(f"路径超出工作区: {path}")
        return resolved

    def _read_file(self, path: str, offset: int = 0, limit: int = 0) -> str:
        p = self._resolve_path(path)
        if not p.exists():
            return f"文件不存在: {path}"
        if p.is_dir():
            items = sorted(p.iterdir())
            lines = [f"📁 {i.name}/" if i.is_dir() else f"📄 {i.name} ({i.stat().st_size}B)" for i in items]
            return f"这是一个目录: {path}\n" + "\n".join(lines[:50])
        content = p.read_text()
        if limit > 0 and offset >= 0:
            lines = content.split('\n')
            content = '\n'.join(lines[offset:offset+limit])
        elif len(content) > 8000:
            content = content[:8000] + f"\n...[省略 {len(content)-8000} 字符]"
        return content

    def _write_file(self, path: str, content: str) -> str:
        p = self._resolve_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        lines = content.count('\n') + 1
        return f"写入成功: {path} ({len(content)} 字符, {lines} 行)"

    def _list_dir(self, path: str) -> str:
        p = self._resolve_path(path)
        if not p.exists():
            return f"目录不存在: {path}"
        if not p.is_dir():
            return f"不是目录: {path}"
        
        items = []
        for item in sorted(p.iterdir()):
            prefix = "📁" if item.is_dir() else "📄"
            size = item.stat().st_size if item.is_file() else 0
            items.append(f"{prefix} {item.name} ({size}B)" if item.is_file() else f"{prefix} {item.name}")
        
        if not items:
            return f"目录为空: {path}"
        return "\n".join(items)

    async def _run_shell(self, command: str) -> str:
        # 安全检查: 禁止危险命令
        dangerous = ["rm -rf", "sudo", "chmod 777", "> /dev/", "mkfs", "dd if="]
        for d in dangerous:
            if d in command.lower():
                return f"安全限制: 禁止执行 '{d}'"
        
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(self.workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=60
            )
            
            result = ""
            if stdout:
                result += stdout.decode()[:2000]
            if stderr:
                result += "\n[stderr]\n" + stderr.decode()[:1000]
            
            return result.strip() or f"命令执行完成 (exit={proc.returncode})"
        except asyncio.TimeoutError:
            return "命令超时(60秒)"
        except Exception as e:
            return f"执行失败: {e}"
