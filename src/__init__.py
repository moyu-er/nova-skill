"""
Nova - AI Agent Framework with Skills and Tools
"""

__version__ = "0.1.0"

# Core types
from .core import (
    ModelType,
    EventType,
    ContentEvent,
    ToolCallEvent,
    ToolResultEvent,
    ErrorEvent,
    ReactEvent,
)

# Skills
from .skills import (
    Skill,
    SkillRegistry,
    Tool,
    get_registry,
)

# Tasks
from .tasks import (
    TaskStatus,
    Task,
    TaskPlan,
    TaskManager,
    TaskPlanner,
)

# Agent
from .agent import (
    Agent,
    AgentConfig,
    ModelFactory,
)

# Display
from .display import (
    Colors,
    DisplayConfig,
    ProgressDisplay,
    SimpleProgressDisplay,
)

__all__ = [
    # Version
    "__version__",
    # Core types
    "ModelType",
    "EventType",
    "ContentEvent",
    "ToolCallEvent",
    "ToolResultEvent",
    "ErrorEvent",
    "ReactEvent",
    # Skills
    "Skill",
    "SkillRegistry",
    "Tool",
    "get_registry",
    # Tasks
    "TaskStatus",
    "Task",
    "TaskPlan",
    "TaskManager",
    "TaskPlanner",
    # Agent
    "Agent",
    "AgentConfig",
    "ModelFactory",
    # Display
    "Colors",
    "DisplayConfig",
    "ProgressDisplay",
    "SimpleProgressDisplay",
]
