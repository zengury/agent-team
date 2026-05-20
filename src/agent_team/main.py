"""CLI entry point for 西游Agent团队."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt

from .orchestrator import AgentTeam

console = Console()

CONFIG_ROOT = Path(__file__).parent.parent.parent / "config"


@click.group()
@click.option("--config-dir", "-c", default=str(CONFIG_ROOT),
              help="Path to config directory")
@click.pass_context
def cli(ctx, config_dir):
    """🏔️ 西游Agent团队 — 唐僧+八戒+悟空+沙僧+白龙马 为你取经！
    
    唐僧(协调) · 八戒(产品) · 悟空(开发) · 沙僧(测试) · 白龙马(客户成功)
    """
    ctx.ensure_object(dict)
    ctx.obj["config_dir"] = Path(config_dir)
    ctx.obj["team"] = None


def _get_team(ctx) -> AgentTeam:
    if ctx.obj["team"] is None:
        config_dir = Path(ctx.obj["config_dir"])
        agents_path = config_dir / "agents.yaml"
        workflows_path = config_dir / "workflows.yaml"
        if not agents_path.exists():
            console.print(f"[red]配置未找到: {agents_path}[/red]")
            sys.exit(1)
        ctx.obj["team"] = AgentTeam(
            config_path=str(agents_path),
            workflows_path=str(workflows_path),
            base_workspace=str(Path.cwd() / "workspaces"),
        )
    return ctx.obj["team"]


@cli.command()
@click.argument("project_name")
@click.option("--transcript", "-t", help="客户对话记录路径")
def init(project_name, transcript):
    """初始化新的取经项目（客户项目）"""
    team = _get_team(click.get_current_context())
    transcript_text = ""
    if transcript:
        tp = Path(transcript)
        if tp.exists():
            transcript_text = tp.read_text()
    ws = team.init_project(project_name, transcript_text)
    console.print(Panel.fit(
        f"[bold green]✅ 项目 '{project_name}' 已就绪[/bold green]\n"
        f"📁 工作区: {ws}\n"
        f"🏔️ 取经队伍整装待发！",
        title="西游Agent团队"
    ))


@cli.command()
@click.argument("transcript_path", type=click.Path(exists=True))
def analyze(transcript_path):
    """📋 将客户对话记录提交给唐僧分析"""
    team = _get_team(click.get_current_context())
    if not team._workspace:
        name = Path(transcript_path).stem
        team.init_project(name)
    transcript = Path(transcript_path).read_text()
    console.print("[bold]👑 唐僧正在分析客户对话…[/bold]\n")
    response = asyncio.run(team.tangseng_analyze(transcript))
    console.print(Panel(Markdown(response), title="唐僧的分析",
                        border_style="gold1"))


@cli.command()
@click.argument("message", required=False)
def chat(message):
    """💬 与唐僧对话讨论项目"""
    team = _get_team(click.get_current_context())
    if message:
        response = asyncio.run(team.chat_with_tangseng(message))
        console.print(Panel(Markdown(response), title="👑 唐僧",
                            border_style="gold1"))
    else:
        console.print("[bold]💬 与唐僧对话 (输入 exit 退出)[/bold]\n")
        while True:
            try:
                msg = Prompt.ask("\n[bold green]师父[/bold green]")
                if msg.lower() in ("exit", "quit", "q"):
                    break
                response = asyncio.run(team.chat_with_tangseng(msg))
                console.print()
                console.print(Panel(Markdown(response), title="👑 唐僧",
                                    border_style="gold1"))
            except (KeyboardInterrupt, EOFError):
                break
        console.print("\n[dim]对话结束。阿弥陀佛。[/dim]")


@cli.command()
@click.argument("workflow_name", default="qujing")
@click.option("--project", "-p", help="项目名称")
def workflow(workflow_name, project):
    """🚀 启动取经工作流: qujing(完整取经) / tanlu(快速探路) / xiance(军师献策)"""
    team = _get_team(click.get_current_context())
    if project:
        team.init_project(project)
    if not team._workspace:
        # Auto-detect from workspaces
        workspaces = sorted(
            [p for p in Path("workspaces").glob("*") if p.is_dir() and not p.name.startswith(".")],
            key=lambda p: p.stat().st_mtime, reverse=True
        )
        if workspaces:
            latest = workspaces[0]
            team.init_project(latest.name)
            console.print(f"[dim]自动检测到项目: {latest.name}[/dim]\n")
        else:
            console.print("[red]请先用 init 或 analyze 初始化项目[/red]")
            sys.exit(1)
    console.print(f"[bold]🚀 开始取经: {workflow_name}[/bold]")
    run = asyncio.run(team.run_workflow(workflow_name))
    table = Table(title=f"取经路线: {workflow_name}")
    table.add_column("阶段", style="cyan")
    table.add_column("执行者", style="magenta")
    table.add_column("状态")
    for phase in run.phases:
        icon = {"done": "✅", "failed": "❌", "skipped": "⏭️"}.get(phase.status, "❓")
        table.add_row(phase.phase_name, phase.agent_name, f"{icon} {phase.status}")
    console.print(table)


@cli.command()
def status():
    """📊 查看当前项目状态"""
    team = _get_team(click.get_current_context())
    s = team.get_status()
    if not s["project"]:
        console.print("[yellow]当前无活跃项目[/yellow]")
        return
    console.print(Panel.fit(
        f"[bold]项目:[/bold] {s['project']}\n"
        f"[bold]工作区:[/bold] {s['workspace']}\n"
        f"[bold]对话记录:[/bold] {'✅' if s['has_transcript'] else '❌'}\n"
        f"[bold]文档数:[/bold] {len(s['documents'])}",
        title="项目状态"
    ))
    if s["documents"]:
        for doc in s["documents"]:
            console.print(f"  📄 {doc}")


@cli.command()
def agents():
    """👥 查看取经队伍"""
    team = _get_team(click.get_current_context())
    agents_list = team.list_agents()
    table = Table(title="🏔️ 西游取经队伍")
    table.add_column("角色", style="cyan")
    table.add_column("法号", style="yellow")
    table.add_column("模型", style="green")
    table.add_column("性格", style="magenta")
    for a in agents_list:
        table.add_row(
            f"{a['emoji']} {a['role']}",
            a['name'],
            a['model'],
            a.get('personality', ''),
        )
    console.print(table)


@cli.command()
def control_plane():
    """🖥️ 启动实时控制面板 (http://localhost:8866)"""
    try:
        from .control_plane.server import main as cp_main
        console.print(Panel.fit(
            "[bold green]🖥️ 控制面板启动中…[/bold green]\n"
            "📍 http://localhost:8866\n"
            "📡 WebSocket: ws://localhost:8866/ws\n\n"
            "打开浏览器查看取经队伍的实时运行状态！",
            title="西游 Control Plane"
        ))
        cp_main()
    except ImportError as e:
        console.print(f"[red]缺少依赖: {e}[/red]")
        console.print("请运行: pip install fastapi uvicorn")


@cli.command()
@click.argument("transcript_path", type=click.Path(exists=True))
def submit(transcript_path):
    """📨 提交对话给唐僧，自动解析委派并执行"""
    team = _get_team(click.get_current_context())
    if not team._workspace:
        name = Path(transcript_path).stem
        team.init_project(name)
    transcript = Path(transcript_path).read_text()
    console.print("[bold]👑 提交对话给唐僧…[/bold]\n")
    response = team.chat_with_tangseng_sync(
        "请分析这份客户对话记录，给出分析和委派任务"
    )
    console.print(Panel(Markdown(response), title="唐僧分析 & 委派",
                        border_style="gold1"))
    tasks = team.parse_delegations(response)
    if tasks:
        console.print(f"\n[bold]📋 解析到 {len(tasks)} 个委派任务[/bold]")
        for t in tasks:
            console.print(f"  @{t.agent_name}: {t.description[:100]}...")
        if click.confirm("\n是否立即执行？"):
            results = asyncio.run(team.delegate_and_collect(response))
            for agent_name, output in results.items():
                console.print(Panel(
                    output[:500] + ("..." if len(output) > 500 else ""),
                    title=f"{agent_name} 产出", border_style="green"))
    else:
        console.print("[dim]未发现委派指令[/dim]")


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
