"""
Task Manager - 任务规划与进度追踪

"""
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import threading


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"          # 待处理
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 已取消


@dataclass
class Task:
    """任务定义"""
    id: int
    subject: str                    # 任务主题
    description: str = ""           # 任务描述
    status: TaskStatus = TaskStatus.PENDING
    blocked_by: List[int] = field(default_factory=list)   # 依赖的任务ID
    blocks: List[int] = field(default_factory=list)       # 阻塞的任务ID
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    result: Optional[str] = None    # 执行结果
    error: Optional[str] = None     # 错误信息

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status.value,
            "blocked_by": self.blocked_by,
            "blocks": self.blocks,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=data["id"],
            subject=data["subject"],
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            blocked_by=data.get("blocked_by", []),
            blocks=data.get("blocks", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
            result=data.get("result"),
            error=data.get("error"),
        )


@dataclass
class TaskPlan:
    """任务计划"""
    id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    query: str = ""                 # 原始查询
    tasks: List[Task] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    current_task_index: int = 0

    @property
    def total_tasks(self) -> int:
        return len(self.tasks)

    @property
    def completed_tasks(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)

    @property
    def progress_percentage(self) -> float:
        if not self.tasks:
            return 0.0
        return (self.completed_tasks / len(self.tasks)) * 100

    @property
    def is_completed(self) -> bool:
        return all(t.status == TaskStatus.COMPLETED for t in self.tasks)

    def get_current_task(self) -> Optional[Task]:
        """获取当前正在执行的任务"""
        for task in self.tasks:
            if task.status == TaskStatus.IN_PROGRESS:
                return task
        # 如果没有进行中的，返回第一个待处理的
        for task in self.tasks:
            if task.status == TaskStatus.PENDING and not task.blocked_by:
                return task
        return None

    def get_ready_tasks(self) -> List[Task]:
        """获取可以执行的任务（待处理且依赖已完成）"""
        ready = []
        for task in self.tasks:
            if task.status == TaskStatus.PENDING:
                # 检查所有依赖是否已完成
                deps_completed = all(
                    self.get_task_by_id(dep_id).status == TaskStatus.COMPLETED
                    for dep_id in task.blocked_by
                )
                if deps_completed:
                    ready.append(task)
        return ready

    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        """通过ID获取任务"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None


class TaskManager:
    """任务管理器 - 负责任务的CRUD和依赖管理"""

    def __init__(self, tasks_dir: Path = None):
        self.tasks_dir = tasks_dir or Path(".tasks")
        self.tasks_dir.mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self._current_plan: Optional[TaskPlan] = None
        self._progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable):
        """设置进度更新回调函数"""
        self._progress_callback = callback

    def _notify_progress(self):
        """通知进度更新"""
        if self._progress_callback and self._current_plan:
            self._progress_callback(self._current_plan)

    def create_plan(self, query: str, tasks_data: List[dict]) -> TaskPlan:
        """创建任务计划"""
        with self._lock:
            plan = TaskPlan(query=query)

            for i, data in enumerate(tasks_data, 1):
                task = Task(
                    id=i,
                    subject=data.get("subject", f"Task {i}"),
                    description=data.get("description", ""),
                    blocked_by=data.get("blocked_by", []),
                    blocks=data.get("blocks", []),
                )
                plan.tasks.append(task)

            self._current_plan = plan
            self._save_plan(plan)
            self._notify_progress()
            return plan

    def update_task_status(self, task_id: int, status: TaskStatus,
                          result: str = None, error: str = None) -> Optional[Task]:
        """更新任务状态"""
        with self._lock:
            if not self._current_plan:
                return None

            task = self._current_plan.get_task_by_id(task_id)
            if not task:
                return None

            task.status = status
            if result:
                task.result = result
            if error:
                task.error = error

            if status == TaskStatus.COMPLETED:
                task.completed_at = datetime.now().isoformat()
                # 更新依赖关系
                self._update_dependencies(task_id)

            self._save_plan(self._current_plan)
            self._notify_progress()
            return task

    def _update_dependencies(self, completed_task_id: int):
        """更新任务依赖关系 - 当一个任务完成时"""
        for task in self._current_plan.tasks:
            if completed_task_id in task.blocked_by:
                task.blocked_by.remove(completed_task_id)

    def get_next_task(self) -> Optional[Task]:
        """获取下一个可执行的任务"""
        with self._lock:
            if not self._current_plan:
                return None

            ready_tasks = self._current_plan.get_ready_tasks()
            return ready_tasks[0] if ready_tasks else None

    def complete_plan(self):
        """完成任务计划"""
        with self._lock:
            if self._current_plan:
                self._current_plan.completed_at = datetime.now().isoformat()
                self._save_plan(self._current_plan)
                self._notify_progress()

    def get_current_plan(self) -> Optional[TaskPlan]:
        """获取当前任务计划"""
        with self._lock:
            return self._current_plan

    def _save_plan(self, plan: TaskPlan):
        """保存任务计划到文件"""
        plan_file = self.tasks_dir / f"plan_{plan.id}.json"
        data = {
            "id": plan.id,
            "query": plan.query,
            "created_at": plan.created_at,
            "completed_at": plan.completed_at,
            "tasks": [t.to_dict() for t in plan.tasks],
        }
        plan_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def load_plan(self, plan_id: str) -> Optional[TaskPlan]:
        """从文件加载任务计划"""
        plan_file = self.tasks_dir / f"plan_{plan_id}.json"
        if not plan_file.exists():
            return None

        data = json.loads(plan_file.read_text())
        plan = TaskPlan(
            id=data["id"],
            query=data["query"],
            created_at=data["created_at"],
            completed_at=data.get("completed_at"),
        )
        plan.tasks = [Task.from_dict(t) for t in data["tasks"]]
        self._current_plan = plan
        return plan

    def list_all_plans(self) -> List[str]:
        """列出所有任务计划"""
        plans = []
        for f in sorted(self.tasks_dir.glob("plan_*.json"), reverse=True):
            plans.append(f.stem.replace("plan_", ""))
        return plans

    def clear_current_plan(self):
        """清除当前任务计划"""
        with self._lock:
            self._current_plan = None
