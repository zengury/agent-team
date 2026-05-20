"""西游Agent定义：八戒、悟空、沙僧、白龙马."""

from pathlib import Path

from .base import BaseAgent, AgentConfig, Task


class BajieAgent(BaseAgent):
    """八戒 — 产品经理 / 创意总监"""

    def __init__(self, config, llm=None, tool_registry=None):
        super().__init__(config, llm, tool_registry)

    async def execute(self, task: Task, workspace: Path) -> str:
        output = await super().execute(task, workspace)
        prd_path = workspace / "docs" / "PRD.md"
        prd_path.parent.mkdir(parents=True, exist_ok=True)
        prd_path.write_text(output)
        return output


class WuKongAgent(BaseAgent):
    """悟空 — 核心开发者 / 技术担当"""

    def __init__(self, config, llm=None, tool_registry=None):
        super().__init__(config, llm, tool_registry)

    async def execute(self, task: Task, workspace: Path) -> str:
        prd_path = workspace / "docs" / "PRD.md"
        if prd_path.exists():
            prd_content = prd_path.read_text()
            task.description = (
                f"📋 八戒的PRD:\n\n{prd_content}\n\n"
                f"---\n🐵 悟空你的任务:\n{task.description}"
            )
        output = await super().execute(task, workspace)
        impl_path = workspace / "docs" / "IMPLEMENTATION.md"
        impl_path.parent.mkdir(parents=True, exist_ok=True)
        impl_path.write_text(output)
        return output


class ShaSengAgent(BaseAgent):
    """沙僧 — 测试工程师 / 质量守门人"""

    def __init__(self, config, llm=None, tool_registry=None):
        super().__init__(config, llm, tool_registry)

    async def execute(self, task: Task, workspace: Path) -> str:
        context_parts = []
        prd_path = workspace / "docs" / "PRD.md"
        impl_path = workspace / "docs" / "IMPLEMENTATION.md"
        
        if prd_path.exists():
            context_parts.append(f"## 八戒的PRD\n\n{prd_path.read_text()}")
        if impl_path.exists():
            context_parts.append(f"## 悟空的实现\n\n{impl_path.read_text()}")
        
        if context_parts:
            task.description = (
                "📋 项目背景:\n\n" + "\n\n---\n\n".join(context_parts)
                + f"\n\n---\n🐟 沙僧你的测试任务:\n{task.description}"
            )
        
        output = await super().execute(task, workspace)
        test_path = workspace / "docs" / "TEST_REPORT.md"
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(output)
        return output


class BaiLongMaAgent(BaseAgent):
    """白龙马 — 客户成功 / 服务担当"""

    def __init__(self, config, llm=None, tool_registry=None):
        super().__init__(config, llm, tool_registry)

    async def execute(self, task: Task, workspace: Path) -> str:
        context_parts = []
        prd_path = workspace / "docs" / "PRD.md"
        impl_path = workspace / "docs" / "IMPLEMENTATION.md"
        
        if prd_path.exists():
            context_parts.append(f"## 八戒的PRD\n\n{prd_path.read_text()}")
        if impl_path.exists():
            context_parts.append(f"## 悟空的实现\n\n{impl_path.read_text()}")
        
        if context_parts:
            task.description = (
                "📋 项目背景:\n\n" + "\n\n---\n\n".join(context_parts)
                + f"\n\n---\n🐉 白龙马你的任务:\n{task.description}"
            )
        
        output = await super().execute(task, workspace)
        client_docs_path = workspace / "docs" / "client" / "DELIVERY.md"
        client_docs_path.parent.mkdir(parents=True, exist_ok=True)
        client_docs_path.write_text(output)
        return output
