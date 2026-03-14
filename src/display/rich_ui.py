"""
Rich-based Terminal UI - 使用 Rich 库的终端界面组件

跨平台支持: Windows, Linux, macOS
"""
from typing import Optional, List
from datetime import datetime

from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.align import Align

from ..tasks.manager import TaskPlan, Task, TaskStatus


class TaskSidebar:
    """任务侧边栏组件"""
    
    def __init__(self, width: int = 35):
        self.width = width
        self.current_plan: Optional[TaskPlan] = None
        
    def _get_status_style(self, status: TaskStatus) -> str:
        """获取状态样式"""
        styles = {
            TaskStatus.PENDING: "dim",
            TaskStatus.IN_PROGRESS: "yellow bold",
            TaskStatus.COMPLETED: "green",
            TaskStatus.FAILED: "red",
            TaskStatus.CANCELLED: "dim strike",
        }
        return styles.get(status, "white")
    
    def _get_status_icon(self, status: TaskStatus) -> str:
        """获取状态图标"""
        icons = {
            TaskStatus.PENDING: "○",
            TaskStatus.IN_PROGRESS: "◐",
            TaskStatus.COMPLETED: "✓",
            TaskStatus.FAILED: "✗",
            TaskStatus.CANCELLED: "⊘",
        }
        return icons.get(status, "?")
    
    def render(self, plan: Optional[TaskPlan] = None) -> Panel:
        """渲染侧边栏"""
        if plan is None:
            plan = self.current_plan
        
        if not plan or not plan.tasks:
            return Panel(
                Text("No active task plan", style="dim"),
                title="[bold cyan]📋 Tasks[/bold cyan]",
                width=self.width,
                border_style="blue"
            )
        
        # 更新当前计划
        self.current_plan = plan
        
        # 构建内容
        content_lines = []
        
        # 进度概览
        total = len(plan.tasks)
        completed = plan.completed_tasks
        percentage = plan.progress_percentage
        
        content_lines.append(f"[bold]{completed}/{total}[/bold] completed")
        content_lines.append(f"[green]{percentage:.0f}%[/green] progress")
        content_lines.append("")
        
        # 任务列表
        for task in plan.tasks:
            icon = self._get_status_icon(task.status)
            style = self._get_status_style(task.status)
            
            # 截断长文本
            subject = task.subject[:25] + "..." if len(task.subject) > 25 else task.subject
            
            if task.blocked_by:
                subject += f" [dim](←{task.blocked_by})[/dim]"
            
            line = f"[{style}]{icon} {subject}[/{style}]"
            content_lines.append(line)
        
        content = "\n".join(content_lines)
        
        return Panel(
            content,
            title=f"[bold cyan]📋 Tasks[/bold cyan] [dim]{plan.id[:8]}[/dim]",
            width=self.width,
            border_style="blue"
        )


class RichProgressDisplay:
    """基于 Rich 的进度显示"""
    
    def __init__(self, sidebar_width: int = 35):
        self.console = Console()
        self.sidebar = TaskSidebar(width=sidebar_width)
        self.sidebar_width = sidebar_width
        self.live: Optional[Live] = None
        self.main_content: List[str] = []
        
    def start(self):
        """启动 Live 显示"""
        if self.live is None:
            layout = self._create_layout()
            self.live = Live(
                layout,
                console=self.console,
                refresh_per_second=4,
                screen=False  # 不使用全屏模式，保持滚动
            )
            self.live.start()
    
    def stop(self):
        """停止 Live 显示"""
        if self.live:
            self.live.stop()
            self.live = None
    
    def _create_layout(self, plan: Optional[TaskPlan] = None) -> Layout:
        """创建布局"""
        layout = Layout()
        
        # 分割为主区域和侧边栏
        layout.split_row(
            Layout(name="main", ratio=1),
            Layout(name="sidebar", size=self.sidebar_width)
        )
        
        # 主区域显示内容
        main_text = "\n".join(self.main_content[-20:])  # 最近 20 行
        layout["main"].update(Panel(
            main_text or "[dim]Waiting for input...[/dim]",
            border_style="dim"
        ))
        
        # 侧边栏显示任务
        layout["sidebar"].update(self.sidebar.render(plan))
        
        return layout
    
    def update(self, plan: Optional[TaskPlan] = None):
        """更新显示"""
        if self.live:
            self.live.update(self._create_layout(plan))
    
    def add_message(self, message: str, style: str = ""):
        """添加消息到主区域"""
        if style:
            self.main_content.append(f"[{style}]{message}[/{style}]")
        else:
            self.main_content.append(message)
        
        # 保持最近 100 行
        if len(self.main_content) > 100:
            self.main_content = self.main_content[-100:]
        
        if self.live:
            self.live.update(self._create_layout(self.sidebar.current_plan))
    
    def print_summary(self, plan: TaskPlan):
        """打印任务汇总"""
        table = Table(title="Task Plan Summary", show_header=True)
        table.add_column("Status", style="cyan", width=8)
        table.add_column("Task", style="white")
        table.add_column("Result", style="dim")
        
        for task in plan.tasks:
            icon = self.sidebar._get_status_icon(task.status)
            style = self.sidebar._get_status_style(task.status)
            
            result = task.result[:50] + "..." if task.result and len(task.result) > 50 else (task.result or "")
            
            table.add_row(
                f"[{style}]{icon}[/{style}]",
                task.subject,
                result
            )
        
        self.console.print(table)


class SimpleRichDisplay:
    """简化版 Rich 显示 - 不使用 Live，直接输出"""
    
    def __init__(self):
        self.console = Console()
        self.sidebar = TaskSidebar()
        self._printed_tasks = set()
    
    def update(self, plan: TaskPlan):
        """更新进度（简化版，只打印变化）"""
        if not plan or not plan.tasks:
            return
        
        for task in plan.tasks:
            task_key = f"{task.id}:{task.status.value}"
            if task_key not in self._printed_tasks:
                self._printed_tasks.add(task_key)
                
                icon = self.sidebar._get_status_icon(task.status)
                style = self.sidebar._get_status_style(task.status)
                
                if task.status == TaskStatus.IN_PROGRESS:
                    self.console.print(f"[{style}]{icon} Starting: {task.subject}[/{style}]")
                elif task.status == TaskStatus.COMPLETED:
                    self.console.print(f"[{style}]{icon} Completed: {task.subject}[/{style}]")
                elif task.status == TaskStatus.FAILED:
                    self.console.print(f"[red]{icon} Failed: {task.subject}[/red]")
    
    def print_summary(self, plan: TaskPlan):
        """打印任务汇总"""
        total = len(plan.tasks)
        completed = sum(1 for t in plan.tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in plan.tasks if t.status == TaskStatus.FAILED)
        
        self.console.print(f"\n[bold cyan]📊 Task Summary: {completed}/{total} completed", end="")
        if failed > 0:
            self.console.print(f", [red]{failed} failed[/red]")
        else:
            self.console.print()
        
        for task in plan.tasks:
            icon = self.sidebar._get_status_icon(task.status)
            style = self.sidebar._get_status_style(task.status)
            self.console.print(f"  [{style}]{icon}[/{style}] {task.subject}")
    
    def reset(self):
        """重置状态"""
        self._printed_tasks.clear()


# 兼容性导出
__all__ = [
    'TaskSidebar',
    'RichProgressDisplay', 
    'SimpleRichDisplay',
]
