"""
Progress Display tests - 测试进度显示组件
"""

import pytest
from src import SimpleProgressDisplay
from src import TaskPlan, Task, TaskStatus


class TestSimpleProgressDisplay:
    """测试 SimpleProgressDisplay"""

    def test_init(self):
        """测试初始化"""
        display = SimpleProgressDisplay()
        assert display._current_plan is None
        assert display._printed_tasks == set()

    def test_get_status_icon(self):
        """测试状态图标"""
        display = SimpleProgressDisplay()

        assert display._get_status_icon(TaskStatus.PENDING) == "○"
        assert display._get_status_icon(TaskStatus.IN_PROGRESS) == "◎"
        assert display._get_status_icon(TaskStatus.COMPLETED) == "✓"
        assert display._get_status_icon(TaskStatus.FAILED) == "✗"

    def test_update_tracks_printed_tasks(self):
        """测试更新跟踪已打印任务"""
        display = SimpleProgressDisplay()

        plan = TaskPlan()
        plan.tasks = [
            Task(id=1, subject="Task 1", status=TaskStatus.IN_PROGRESS),
        ]

        display.update(plan)

        # 检查任务被标记为已打印
        assert "1:in_progress" in display._printed_tasks

    def test_reset_clears_state(self):
        """测试重置清除状态"""
        display = SimpleProgressDisplay()

        plan = TaskPlan()
        plan.tasks = [Task(id=1, subject="Task 1", status=TaskStatus.COMPLETED)]

        display.update(plan)
        display.reset()

        assert display._printed_tasks == set()
        assert display._current_plan is None


class TestTaskPlanProgress:
    """测试任务计划进度计算"""

    def test_empty_plan(self):
        """测试空计划"""
        plan = TaskPlan()
        assert plan.total_tasks == 0
        assert plan.completed_tasks == 0
        assert plan.progress_percentage == 0.0
        assert plan.is_completed is True  # 空计划视为完成

    def test_plan_with_tasks(self):
        """测试有任务的计划"""
        plan = TaskPlan()
        plan.tasks = [
            Task(id=1, subject="Task 1", status=TaskStatus.COMPLETED),
            Task(id=2, subject="Task 2", status=TaskStatus.PENDING),
            Task(id=3, subject="Task 3", status=TaskStatus.IN_PROGRESS),
        ]

        assert plan.total_tasks == 3
        assert plan.completed_tasks == 1
        assert abs(plan.progress_percentage - 33.33) < 0.01  # 约等于

    def test_all_completed(self):
        """测试全部完成"""
        plan = TaskPlan()
        plan.tasks = [
            Task(id=1, subject="Task 1", status=TaskStatus.COMPLETED),
            Task(id=2, subject="Task 2", status=TaskStatus.COMPLETED),
        ]

        assert plan.is_completed is True
        assert plan.progress_percentage == 100.0


class TestTaskDependencies:
    """测试任务依赖"""

    def test_task_with_dependencies(self):
        """测试有依赖的任务"""
        task = Task(
            id=2,
            subject="Task 2",
            blocked_by=[1],  # 依赖 Task 1
        )

        assert task.blocked_by == [1]

    def test_get_task_by_id(self):
        """测试通过 ID 获取任务"""
        plan = TaskPlan()
        plan.tasks = [
            Task(id=1, subject="Task 1"),
            Task(id=2, subject="Task 2"),
        ]

        task = plan.get_task_by_id(2)
        assert task is not None
        assert task.subject == "Task 2"

        task = plan.get_task_by_id(999)
        assert task is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
