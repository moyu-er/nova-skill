"""
Task Planning Tools - Task management operations
"""
from typing import Annotated, Optional, List

from langchain_core.tools import tool

from ..tasks import TaskStatus, TaskManager
from . import get_global_task_manager


@tool
def create_task_plan(
    query: Annotated[str, "The task description to plan"],
    tasks: Annotated[List[dict], "List of tasks to create. Each task should have 'subject' (str), optional 'description' (str), optional 'blocked_by' (list of task IDs that must be completed first)"] = None
) -> str:
    """
    Create a task plan for complex multi-step requests.

    Use this tool when the user has a complex request that needs to be broken down into steps.
    The plan will be saved and can be tracked.

    Args:
        query: The complex task description to plan
        tasks: List of task definitions. Example:
            [
                {"subject": "Task 1", "description": "Do first thing"},
                {"subject": "Task 2", "description": "Do second thing", "blocked_by": [1]},
                {"subject": "Task 3", "description": "Do third thing", "blocked_by": [2]}
            ]

    Returns:
        Task plan details with task list
    """
    try:
        task_manager = get_global_task_manager()
        
        # If no tasks provided, create a simple single-task plan
        if not tasks:
            tasks = [{"subject": query, "description": ""}]
        
        # Create the plan
        plan = task_manager.create_plan(query, tasks)
        
        # Build response
        lines = [f"✓ Task plan created with {len(plan.tasks)} tasks", ""]
        lines.append(f"Plan ID: {plan.id}")
        lines.append("")
        
        for task in plan.tasks:
            deps = f" (depends on: {task.blocked_by})" if task.blocked_by else ""
            lines.append(f"  ○ #{task.id}: {task.subject}{deps}")
            if task.description:
                lines.append(f"      {task.description}")
        
        lines.append("")
        lines.append("Use update_task_status to mark tasks as completed.")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error creating task plan: {e}"


@tool
def get_task_status() -> str:
    """
    Get current task plan status and progress.

    Returns:
        Current task plan status with progress information
    """
    try:
        task_manager = get_global_task_manager()
        plan = task_manager.get_current_plan()
        
        if not plan:
            return "No active task plan. Use create_task_plan to create one."
        
        # Build status report
        lines = [
            f"Task Plan: {plan.id}",
            f"Query: {plan.query}",
            f"Progress: {plan.completed_tasks}/{plan.total_tasks} ({plan.progress_percentage:.1f}%)",
            ""
        ]
        
        # Status markers
        markers = {
            TaskStatus.PENDING: "[ ]",
            TaskStatus.IN_PROGRESS: "[>]",
            TaskStatus.COMPLETED: "[x]",
            TaskStatus.FAILED: "[!]",
            TaskStatus.CANCELLED: "[-]"
        }
        
        for task in plan.tasks:
            marker = markers.get(task.status, "[?]")
            deps = f" (blocked by: {task.blocked_by})" if task.blocked_by else ""
            lines.append(f"{marker} #{task.id}: {task.subject}{deps}")
            
            if task.result:
                lines.append(f"      Result: {task.result[:100]}...")
            if task.error:
                lines.append(f"      Error: {task.error}")
        
        if plan.is_completed:
            lines.append("")
            lines.append("✓ All tasks completed!")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error getting task status: {e}"


@tool
def update_task_status(
    task_id: Annotated[int, "Task ID to update"],
    status: Annotated[str, "New status: pending, in_progress, completed, failed, cancelled"],
    result: Annotated[str, "Task result or output"] = "",
    error: Annotated[str, "Error message if task failed"] = ""
) -> str:
    """
    Update a task's status in the current plan.

    Args:
        task_id: The task ID to update
        status: New status (pending, in_progress, completed, failed, cancelled)
        result: Optional task result/output
        error: Optional error message if task failed

    Returns:
        Update confirmation
    """
    try:
        task_manager = get_global_task_manager()
        
        # Validate status
        try:
            task_status = TaskStatus(status.lower())
        except ValueError:
            valid_statuses = [s.value for s in TaskStatus]
            return f"Invalid status '{status}'. Valid statuses: {', '.join(valid_statuses)}"
        
        # Update the task
        task = task_manager.update_task_status(
            task_id=task_id,
            status=task_status,
            result=result if result else None,
            error=error if error else None
        )
        
        if not task:
            return f"Task #{task_id} not found in current plan."
        
        # Build response
        lines = [f"✓ Task #{task_id} updated to '{status}'"]
        
        if result:
            lines.append(f"  Result: {result[:200]}...")
        if error:
            lines.append(f"  Error: {error}")
        
        # Check if all tasks are completed
        plan = task_manager.get_current_plan()
        if plan and plan.is_completed:
            lines.append("")
            lines.append("🎉 All tasks in the plan are now completed!")
        else:
            # Show next ready tasks
            ready_tasks = plan.get_ready_tasks() if plan else []
            if ready_tasks:
                lines.append("")
                lines.append("Ready to start:")
                for t in ready_tasks:
                    lines.append(f"  • #{t.id}: {t.subject}")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error updating task status: {e}"


@tool
def list_task_plans() -> str:
    """
    List all saved task plans.

    Returns:
        List of task plan IDs
    """
    try:
        task_manager = get_global_task_manager()
        plans = task_manager.list_all_plans()
        
        if not plans:
            return "No saved task plans."
        
        lines = ["Saved task plans:", ""]
        for plan_id in plans[:10]:  # Show last 10
            lines.append(f"  • {plan_id}")
        
        if len(plans) > 10:
            lines.append(f"  ... and {len(plans) - 10} more")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error listing task plans: {e}"


@tool
def get_next_task() -> str:
    """
    Get the next task that is ready to be executed.

    Returns:
        Next ready task or message if no tasks are ready
    """
    try:
        task_manager = get_global_task_manager()
        task = task_manager.get_next_task()
        
        if not task:
            plan = task_manager.get_current_plan()
            if not plan:
                return "No active task plan."
            elif plan.is_completed:
                return "All tasks are completed!"
            else:
                return "No tasks are ready. Some tasks may be blocked by dependencies."
        
        lines = [
            f"Next task: #{task.id}",
            f"Subject: {task.subject}",
        ]
        
        if task.description:
            lines.append(f"Description: {task.description}")
        
        if task.blocked_by:
            lines.append(f"Dependencies: {task.blocked_by}")
        
        lines.append("")
        lines.append("Use update_task_status to mark this task as in_progress or completed.")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error getting next task: {e}"
