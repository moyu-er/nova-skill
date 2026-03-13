"""
Task Planning Tools - 任务规划相关工具

为 Agent 提供任务规划能力
"""
import json
from typing import List, Dict, Optional
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

from .manager import TaskManager, TaskPlan, Task, TaskStatus


class TaskPlanner:
    """任务规划器 - 使用 LLM 生成任务计划"""

    PLANNING_PROMPT = """你是一个任务规划专家。请将用户的请求拆解为具体的执行步骤。

要求：
1. 每个步骤应该是原子性的、可执行的任务
2. 识别任务之间的依赖关系
3. 返回 JSON 格式的任务列表

输出格式：
{{"tasks": [
    {{
        "subject": "任务简短描述",
        "description": "详细描述",
        "blocked_by": []
    }}
]}}

注意：
- blocked_by 中的数字是任务在列表中的位置（从1开始）
- 如果任务没有依赖，blocked_by 为空数组 []
- 确保依赖关系不会形成循环

用户请求：{query}
"""

    def __init__(self, llm):
        self.llm = llm
        self.task_manager = TaskManager()

    async def create_plan(self, query: str) -> TaskPlan:
        """创建任务计划"""
        import logging
        logger = logging.getLogger(__name__)

        # 使用 LLM 生成任务计划
        messages = [
            SystemMessage(content="你是一个任务规划专家。请将用户请求拆解为可执行的任务步骤。"),
            HumanMessage(content=self.PLANNING_PROMPT.format(query=query))
        ]

        response = await self.llm.ainvoke(messages)

        # 解析 JSON 响应
        tasks_data = []
        try:
            content = response.content
            logger.debug(f"LLM response content: {content[:200]}...")

            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            content = content.strip()
            logger.debug(f"Extracted JSON: {content[:200]}...")

            data = json.loads(content)

            # 安全获取 tasks
            if isinstance(data, dict) and "tasks" in data:
                tasks_data = data["tasks"]
            elif isinstance(data, list):
                # LLM 可能直接返回了任务列表
                tasks_data = data
            else:
                logger.warning(f"Unexpected response format: {type(data)}")
                tasks_data = []

            # 确保每个任务都有必需的字段
            validated_tasks = []
            for i, task in enumerate(tasks_data):
                if isinstance(task, dict) and "subject" in task:
                    validated_tasks.append({
                        "subject": task.get("subject", f"Task {i+1}"),
                        "description": task.get("description", ""),
                        "blocked_by": task.get("blocked_by", [])
                    })

            tasks_data = validated_tasks if validated_tasks else [{"subject": query, "description": "执行用户请求", "blocked_by": []}]

        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {type(e).__name__}: {e}. Using fallback plan.")
            # 如果解析失败，创建一个简单的单任务计划
            tasks_data = [{"subject": query, "description": "执行用户请求", "blocked_by": []}]

        # 创建任务计划
        plan = self.task_manager.create_plan(query, tasks_data)
        return plan

    def get_next_task(self) -> Optional[Task]:
        """获取下一个可执行的任务"""
        return self.task_manager.get_next_task()

    def update_task_status(self, task_id: int, status: TaskStatus, result: str = None, error: str = None):
        """更新任务状态"""
        return self.task_manager.update_task_status(task_id, status, result, error)

    def get_current_plan(self) -> Optional[TaskPlan]:
        """获取当前任务计划"""
        return self.task_manager.get_current_plan()

    def complete_plan(self):
        """完成任务计划"""
        self.task_manager.complete_plan()
