"""
Task Planning Tools - Task management operations
"""
from typing import Annotated, Optional

from langchain_core.tools import tool

from ..tasks import TaskStatus
from . import get_global_task_manager


@tool
def create_task_plan(query: Annotated[str, "The task description to plan"]) -> str:
    """
    Create a task plan for complex multi-step requests.

    Use this tool when the user has a complex request that needs to be broken down into steps.
    The plan will be saved and can be tracked.

    Args:
        query: The complex task description to plan

    Returns:
        Task plan details with task list
    """
    return "Task plan creation requested"


@tool
def get_task_status() -> str:
    """
    Get current task plan status and progress.

    Returns:
        Current task plan status with progress information
    """
    return "Task status requested"


@tool
def update_task_status(
    task_id: Annotated[int, "Task ID to update"],
    status: Annotated[str, "New status: pending, in_progress, completed, failed"],
    result: Annotated[str, "Task result or output"] = ""
) -> str:
    """
    Update a task's status in the current plan.

    Args:
        task_id: The task ID to update
        status: New status (pending, in_progress, completed, failed)
        result: Optional task result

    Returns:
        Update confirmation
    """
    return f"Task {task_id} status update requested"
