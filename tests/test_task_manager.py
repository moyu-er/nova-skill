"""
Task Manager tests - 测试任务管理功能
"""

import tempfile
import shutil
from pathlib import Path


import pytest
from src import TaskManager, TaskPlan, Task, TaskStatus


class TestTask:
    """测试 Task 类"""

    def test_task_creation(self):
        """测试创建任务"""
        task = Task(
            id=1,
            subject="Test task",
            description="Test description"
        )
        assert task.id == 1
        assert task.subject == "Test task"
        assert task.description == "Test description"
        assert task.status == TaskStatus.PENDING

    def test_task_to_dict(self):
        """测试任务序列化"""
        task = Task(
            id=1,
            subject="Test",
            status=TaskStatus.IN_PROGRESS
        )
        data = task.to_dict()
        assert data["id"] == 1
        assert data["subject"] == "Test"
        assert data["status"] == "in_progress"

    def test_task_from_dict(self):
        """测试任务反序列化"""
        data = {
            "id": 1,
            "subject": "Test",
            "description": "Desc",
            "status": "completed",
            "blocked_by": [2, 3],
            "blocks": [4],
        }
        task = Task.from_dict(data)
        assert task.id == 1
        assert task.status == TaskStatus.COMPLETED
        assert task.blocked_by == [2, 3]


class TestTaskPlan:
    """测试 TaskPlan 类"""

    def test_plan_creation(self):
        """测试创建任务计划"""
        plan = TaskPlan(query="Test query")
        assert plan.query == "Test query"
        assert plan.tasks == []
        assert plan.total_tasks == 0

    def test_plan_progress(self):
        """测试进度计算"""
        plan = TaskPlan()
        plan.tasks = [
            Task(id=1, subject="Task 1", status=TaskStatus.COMPLETED),
            Task(id=2, subject="Task 2", status=TaskStatus.IN_PROGRESS),
            Task(id=3, subject="Task 3", status=TaskStatus.PENDING),
        ]

        assert plan.total_tasks == 3
        assert plan.completed_tasks == 1
        assert abs(plan.progress_percentage - 33.33) < 0.01  # 1/3

    def test_get_current_task(self):
        """测试获取当前任务"""
        plan = TaskPlan()
        plan.tasks = [
            Task(id=1, subject="Task 1", status=TaskStatus.COMPLETED),
            Task(id=2, subject="Task 2", status=TaskStatus.IN_PROGRESS),
        ]

        current = plan.get_current_task()
        assert current.id == 2

    def test_get_ready_tasks(self):
        """测试获取就绪任务"""
        plan = TaskPlan()
        plan.tasks = [
            Task(id=1, subject="Task 1", status=TaskStatus.COMPLETED),
            Task(id=2, subject="Task 2", status=TaskStatus.PENDING, blocked_by=[1]),
            Task(id=3, subject="Task 3", status=TaskStatus.PENDING),  # 无依赖
        ]

        ready = plan.get_ready_tasks()
        # Task 2 的依赖已完成，Task 3 无依赖，所以都应该就绪
        assert len(ready) == 2
        ready_ids = [t.id for t in ready]
        assert 2 in ready_ids
        assert 3 in ready_ids


class TestTaskManager:
    """测试 TaskManager 类"""

    def setup_method(self):
        """每个测试前创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = TaskManager(tasks_dir=Path(self.temp_dir))

    def teardown_method(self):
        """每个测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_plan(self):
        """测试创建任务计划"""
        tasks_data = [
            {"subject": "Task 1", "description": "First task"},
            {"subject": "Task 2", "description": "Second task"},
        ]

        plan = self.manager.create_plan("Test query", tasks_data)

        assert plan.query == "Test query"
        assert len(plan.tasks) == 2
        assert plan.tasks[0].subject == "Task 1"
        assert plan.tasks[1].id == 2

    def test_update_task_status(self):
        """测试更新任务状态"""
        tasks_data = [{"subject": "Task 1"}]
        plan = self.manager.create_plan("Test", tasks_data)

        task = self.manager.update_task_status(1, TaskStatus.IN_PROGRESS)
        assert task.status == TaskStatus.IN_PROGRESS

        task = self.manager.update_task_status(1, TaskStatus.COMPLETED, result="Done")
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "Done"
        assert task.completed_at is not None

    def test_get_next_task(self):
        """测试获取下一个任务"""
        tasks_data = [
            {"subject": "Task 1"},
            {"subject": "Task 2"},
        ]
        self.manager.create_plan("Test", tasks_data)

        next_task = self.manager.get_next_task()
        assert next_task.id == 1

        # 标记第一个为完成
        self.manager.update_task_status(1, TaskStatus.COMPLETED)

        next_task = self.manager.get_next_task()
        assert next_task.id == 2

    def test_dependency_resolution(self):
        """测试依赖解析"""
        tasks_data = [
            {"subject": "Task 1", "id": 1},
            {"subject": "Task 2", "blocked_by": [1]},  # 依赖 Task 1
        ]
        self.manager.create_plan("Test", tasks_data)

        # Task 2 应该被阻塞
        next_task = self.manager.get_next_task()
        assert next_task.id == 1

        # 完成 Task 1
        self.manager.update_task_status(1, TaskStatus.COMPLETED)

        # Task 2 应该就绪
        next_task = self.manager.get_next_task()
        assert next_task.id == 2

    def test_save_and_load_plan(self):
        """测试保存和加载计划"""
        tasks_data = [{"subject": "Task 1"}]
        plan = self.manager.create_plan("Test query", tasks_data)
        plan_id = plan.id

        # 创建新的 manager 加载计划
        new_manager = TaskManager(tasks_dir=Path(self.temp_dir))
        loaded_plan = new_manager.load_plan(plan_id)

        assert loaded_plan is not None
        assert loaded_plan.query == "Test query"
        assert len(loaded_plan.tasks) == 1

    def test_progress_callback(self):
        """测试进度回调"""
        callback_called = [False]

        def callback(plan):
            callback_called[0] = True

        self.manager.set_progress_callback(callback)

        tasks_data = [{"subject": "Task 1"}]
        self.manager.create_plan("Test", tasks_data)

        assert callback_called[0] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
