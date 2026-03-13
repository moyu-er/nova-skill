"""
Progress Display - 终端进度显示组件

支持:
1. 底部状态栏显示当前任务进度
2. 侧边栏风格（使用 ANSI 转义码定位）
3. 任务完成后汇总显示
"""
import sys
import shutil
from typing import Optional, List
from dataclasses import dataclass

from ..tasks.manager import TaskPlan, Task, TaskStatus


class Colors:
    """ANSI 颜色代码"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BG_BLUE = '\033[44m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_GRAY = '\033[100m'


@dataclass
class DisplayConfig:
    """显示配置"""
    show_sidebar: bool = True           # 是否显示侧边栏
    sidebar_width: int = 40             # 侧边栏宽度
    show_progress_bar: bool = True      # 是否显示进度条
    show_task_list: bool = True         # 是否显示任务列表
    refresh_rate: float = 0.1           # 刷新率（秒）


class ProgressDisplay:
    """进度显示器"""

    def __init__(self, config: DisplayConfig = None):
        self.config = config or DisplayConfig()
        self.terminal_width = shutil.get_terminal_size().columns
        self.terminal_height = shutil.get_terminal_size().lines
        self._last_lines_count = 0
        self._is_active = False

    def _get_terminal_size(self):
        """获取终端大小"""
        self.terminal_width = shutil.get_terminal_size().columns
        self.terminal_height = shutil.get_terminal_size().lines

    def _clear_lines(self, count: int):
        """清除指定行数"""
        for _ in range(count):
            sys.stdout.write('\033[F')  # 光标上移一行
            sys.stdout.write('\033[2K')  # 清除整行
        sys.stdout.flush()

    def _move_cursor_up(self, lines: int):
        """光标上移"""
        sys.stdout.write(f'\033[{lines}A')
        sys.stdout.flush()

    def _move_cursor_down(self, lines: int):
        """光标下移"""
        sys.stdout.write(f'\033[{lines}B')
        sys.stdout.flush()

    def _move_cursor_to_column(self, col: int):
        """移动光标到指定列"""
        sys.stdout.write(f'\033[{col}G')
        sys.stdout.flush()

    def _save_cursor(self):
        """保存光标位置"""
        sys.stdout.write('\033[s')
        sys.stdout.flush()

    def _restore_cursor(self):
        """恢复光标位置"""
        sys.stdout.write('\033[u')
        sys.stdout.flush()

    def _hide_cursor(self):
        """隐藏光标"""
        sys.stdout.write('\033[?25l')
        sys.stdout.flush()

    def _show_cursor(self):
        """显示光标"""
        sys.stdout.write('\033[?25h')
        sys.stdout.flush()

    def _get_status_icon(self, status: TaskStatus) -> str:
        """获取状态图标"""
        icons = {
            TaskStatus.PENDING: "○",
            TaskStatus.IN_PROGRESS: "◐",
            TaskStatus.COMPLETED: "✓",
            TaskStatus.FAILED: "✗",
            TaskStatus.CANCELLED: "⊘",
        }
        colors = {
            TaskStatus.PENDING: Colors.DIM,
            TaskStatus.IN_PROGRESS: Colors.YELLOW,
            TaskStatus.COMPLETED: Colors.GREEN,
            TaskStatus.FAILED: Colors.RED,
            TaskStatus.CANCELLED: Colors.DIM,
        }
        icon = icons.get(status, "?")
        color = colors.get(status, Colors.RESET)
        return f"{color}{icon}{Colors.RESET}"

    def _format_progress_bar(self, percentage: float, width: int = 20) -> str:
        """格式化进度条"""
        filled = int(width * percentage / 100)
        empty = width - filled
        bar = "█" * filled + "░" * empty
        color = Colors.GREEN if percentage >= 100 else Colors.YELLOW
        return f"{color}{bar}{Colors.RESET} {percentage:.0f}%"

    def _truncate_text(self, text: str, max_width: int) -> str:
        """截断文本"""
        if len(text) <= max_width:
            return text
        return text[:max_width-3] + "..."

    def render_compact_status(self, plan: TaskPlan) -> str:
        """渲染紧凑状态（单行）"""
        if not plan or not plan.tasks:
            return ""

        total = len(plan.tasks)
        completed = plan.completed_tasks
        percentage = plan.progress_percentage

        # 找到当前任务
        current_task = plan.get_current_task()
        current_name = current_task.subject if current_task else "等待中..."

        # 构建状态行
        progress_bar = self._format_progress_bar(percentage, width=15)
        status_text = f"{Colors.CYAN}[{completed}/{total}]{Colors.RESET} {progress_bar} {Colors.DIM}{current_name}{Colors.RESET}"

        return status_text

    def render_sidebar(self, plan: TaskPlan) -> List[str]:
        """渲染侧边栏内容"""
        if not plan or not plan.tasks:
            return []

        lines = []
        width = self.config.sidebar_width - 2  # 留边距

        # 标题
        lines.append(f"{Colors.BOLD}{Colors.CYAN}📋 Task Plan{Colors.RESET}")
        lines.append("─" * width)

        # 进度概览
        total = len(plan.tasks)
        completed = plan.completed_tasks
        percentage = plan.progress_percentage

        lines.append(f"Progress: {Colors.BOLD}{completed}/{total}{Colors.RESET}")
        lines.append(self._format_progress_bar(percentage, width=width-10))
        lines.append("")

        # 任务列表
        for task in plan.tasks:
            icon = self._get_status_icon(task.status)
            name = self._truncate_text(task.subject, width - 4)

            if task.status == TaskStatus.IN_PROGRESS:
                name = f"{Colors.BOLD}{Colors.YELLOW}{name}{Colors.RESET}"
            elif task.status == TaskStatus.COMPLETED:
                name = f"{Colors.DIM}{name}{Colors.RESET}"

            lines.append(f"{icon} {name}")

        # 底部边框
        lines.append("")
        lines.append("─" * width)

        return lines

    def render_summary(self, plan: TaskPlan) -> str:
        """渲染任务完成后的汇总"""
        if not plan:
            return ""

        lines = []
        lines.append(f"\n{Colors.BOLD}{Colors.GREEN}✅ Task Plan Completed{Colors.RESET}")
        lines.append(f"{Colors.DIM}Query: {plan.query}{Colors.RESET}")
        lines.append("")

        for task in plan.tasks:
            icon = self._get_status_icon(task.status)
            lines.append(f"{icon} {task.subject}")
            if task.result:
                result_preview = task.result[:100].replace('\n', ' ')
                lines.append(f"   {Colors.DIM}{result_preview}{Colors.RESET}")

        lines.append("")
        return "\n".join(lines)

    def print_status_line(self, plan: TaskPlan):
        """打印状态行（在底部）"""
        status = self.render_compact_status(plan)
        if status:
            # 保存光标位置
            self._save_cursor()
            # 移动到底部
            sys.stdout.write(f'\033[{self.terminal_height};0H')
            # 清除行
            sys.stdout.write('\033[2K')
            # 打印状态
            sys.stdout.write(status)
            # 恢复光标
            self._restore_cursor()
            sys.stdout.flush()

    def print_sidebar_inline(self, plan: TaskPlan):
        """在行内打印侧边栏（右侧）"""
        if not self.config.show_sidebar:
            return

        sidebar_lines = self.render_sidebar(plan)
        if not sidebar_lines:
            return

        # 获取当前光标位置
        self._save_cursor()

        # 计算右侧起始位置
        sidebar_start = self.terminal_width - self.config.sidebar_width

        # 打印侧边栏
        for i, line in enumerate(sidebar_lines):
            # 移动光标到右侧位置
            sys.stdout.write(f'\033[{i+1};{sidebar_start}H')
            # 清除到行尾
            sys.stdout.write('\033[K')
            # 打印内容
            sys.stdout.write(line)

        # 恢复光标
        self._restore_cursor()
        sys.stdout.flush()

    def update(self, plan: TaskPlan):
        """更新显示"""
        self._get_terminal_size()

        if self.config.show_sidebar and self.terminal_width > 100:
            # 宽屏显示侧边栏
            self.print_sidebar_inline(plan)
        else:
            # 窄屏显示底部状态
            self.print_status_line(plan)

    def clear(self):
        """清除显示"""
        self._show_cursor()


class SimpleProgressDisplay:
    """简单进度显示 - 不使用 ANSI 转义码，兼容性更好"""

    def __init__(self):
        self._current_plan: Optional[TaskPlan] = None
        self._printed_tasks = set()

    def _get_status_icon(self, status: TaskStatus) -> str:
        """获取状态图标"""
        icons = {
            TaskStatus.PENDING: "○",
            TaskStatus.IN_PROGRESS: "◎",
            TaskStatus.COMPLETED: "✓",
            TaskStatus.FAILED: "✗",
            TaskStatus.CANCELLED: "⊘",
        }
        return icons.get(status, "?")

    def update(self, plan: TaskPlan):
        """更新进度显示"""
        self._current_plan = plan

        if not plan or not plan.tasks:
            return

        # 只打印状态变化的任务
        for task in plan.tasks:
            task_key = f"{task.id}:{task.status.value}"
            if task_key not in self._printed_tasks:
                self._printed_tasks.add(task_key)

                icon = self._get_status_icon(task.status)

                if task.status == TaskStatus.IN_PROGRESS:
                    print(f"\n{Colors.YELLOW}{icon} Starting: {task.subject}{Colors.RESET}")
                elif task.status == TaskStatus.COMPLETED:
                    print(f"{Colors.GREEN}{icon} Completed: {task.subject}{Colors.RESET}")
                elif task.status == TaskStatus.FAILED:
                    print(f"{Colors.RED}{icon} Failed: {task.subject}{Colors.RESET}")

    def print_summary(self, plan: TaskPlan):
        """打印任务汇总"""
        if not plan:
            return

        total = len(plan.tasks)
        completed = sum(1 for t in plan.tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in plan.tasks if t.status == TaskStatus.FAILED)

        print(f"\n{Colors.BOLD}{Colors.CYAN}📊 Task Summary: {completed}/{total} completed", end="")
        if failed > 0:
            print(f", {Colors.RED}{failed} failed{Colors.RESET}")
        else:
            print(Colors.RESET)

        for task in plan.tasks:
            icon = self._get_status_icon(task.status)
            print(f"  {icon} {task.subject}")

    def reset(self):
        """重置状态"""
        self._printed_tasks.clear()
        self._current_plan = None
