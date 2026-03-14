"""
Tools package - Auto-discover all @tool decorated functions

Automatically imports and registers all tools from submodules.
"""
import os
import sys
import importlib
import inspect
from pathlib import Path
from typing import List, Callable, Any

from ..skills import SkillRegistry
from ..tasks import TaskManager

# Global instances
_skill_registry: SkillRegistry = None
_task_manager: TaskManager = None

# Registry of all discovered tools
_all_tools: List[Callable] = []


def set_global_registry(registry: SkillRegistry):
    """Set global skill registry"""
    global _skill_registry
    _skill_registry = registry


def set_global_task_manager(task_manager: TaskManager):
    """Set global task manager"""
    global _task_manager
    _task_manager = task_manager


def get_global_registry() -> SkillRegistry:
    """Get global skill registry (create if not exists)"""
    global _skill_registry
    if _skill_registry is None:
        from ..skills import SkillRegistry
        _skill_registry = SkillRegistry()
    return _skill_registry


def get_global_task_manager() -> TaskManager:
    """Get global task manager (create if not exists)"""
    global _task_manager
    if _task_manager is None:
        from ..tasks import TaskManager
        _task_manager = TaskManager()
    return _task_manager


def _is_tool_function(obj: Any) -> bool:
    """Check if object is a tool function (decorated with @tool)"""
    # Check if it's a StructuredTool (result of @tool decorator)
    if hasattr(obj, 'name') and hasattr(obj, 'invoke'):
        return True
    # Check if it's a callable with _tool attribute (our custom marking)
    if callable(obj) and hasattr(obj, '_is_tool'):
        return True
    return False


def _discover_tools_in_module(module) -> List[Callable]:
    """Discover all tool functions in a module"""
    tools = []
    for name in dir(module):
        if name.startswith('_'):
            continue
        obj = getattr(module, name)
        if _is_tool_function(obj):
            tools.append(obj)
    return tools


def _auto_discover_tools() -> List[Callable]:
    """Auto-discover all tools from tools package"""
    tools = []
    package_dir = Path(__file__).parent

    # Get all .py files in the tools directory
    for file_path in sorted(package_dir.glob('*.py')):
        if file_path.name == '__init__.py':
            continue

        # Use relative import path (e.g., .files, .system)
        module_name = f".{file_path.stem}"
        try:
            # Import the module using relative import
            module = importlib.import_module(module_name, package=__package__)

            # Discover tools in the module
            module_tools = _discover_tools_in_module(module)
            tools.extend(module_tools)

        except Exception as e:
            print(f"Warning: Failed to import {module_name}: {e}", file=sys.stderr)

    return tools


def get_all_tools(registry: SkillRegistry = None, task_manager: TaskManager = None) -> List[Callable]:
    """
    Get all registered tools.

    Args:
        registry: SkillRegistry instance (optional, uses global if not provided)
        task_manager: TaskManager instance (optional, uses global if not provided)

    Returns:
        List of all registered tools
    """
    global _all_tools

    # Set global instances if provided
    if registry is not None:
        set_global_registry(registry)
    if task_manager is not None:
        set_global_task_manager(task_manager)

    # Auto-discover tools if not already done
    if not _all_tools:
        _all_tools = _auto_discover_tools()

    return _all_tools.copy()


def reload_tools():
    """Reload all tools (useful for development)"""
    global _all_tools
    _all_tools = []
    return get_all_tools()


def register_gateway_tools() -> dict:
    """Register all gateway tools from tool modules
    
    Scans all tool modules for register_module_tools functions and calls them.
    This allows flexible registration of tools from any module.
    
    Returns:
        Dict mapping module names to count of registered tools
    """
    from .gateway import get_global_gateway
    
    gateway = get_global_gateway()
    registered = {}
    total = 0
    
    # List of modules that may have gateway tools
    # Each module should have a register_module_tools() function
    gateway_tool_modules = [
        'mut_los_tools',
        # Add new gateway tool modules here
    ]
    
    for module_name in gateway_tool_modules:
        try:
            module = importlib.import_module(f'.{module_name}', package=__package__)
            if hasattr(module, 'register_module_tools'):
                count = module.register_module_tools()
                registered[module_name] = count
                total += count
        except Exception as e:
            print(f"Warning: Failed to register tools from {module_name}: {e}", file=sys.stderr)
    
    # Print summary
    if registered:
        categories = set()
        for tool_name, metadata in gateway._tools.items():
            categories.add(metadata.category)
        
        print(f"✓ Registered {total} gateway tools ({len(categories)} categories)")
        for module, count in registered.items():
            if count > 0:
                print(f"  - {module}: {count} tools")
    
    return registered


# Import and re-export all tools for backward compatibility
from .system import get_system_info, execute_command
from .files import read_file, write_file, list_directory, get_file_info, edit_file, replace_in_file
from .network import search_web, fetch_url
from .time import get_current_time, list_timezones
from .skills import get_available_skills, read_skill_detail
from .tasks import create_task_plan, get_task_status, update_task_status
from .gateway import gateway_call_tool, gateway_query_tool, gateway_tool, ToolGateway, get_global_gateway
from . import mut_los_tools

# Auto-register gateway tools when module is imported
register_gateway_tools()

__all__ = [
    # Functions
    'get_all_tools',
    'set_global_registry',
    'set_global_task_manager',
    'get_global_registry',
    'get_global_task_manager',
    'reload_tools',
    'register_gateway_tools',
    # Basic Tools
    'get_system_info',
    'execute_command',
    'read_file',
    'write_file',
    'list_directory',
    'get_file_info',
    'edit_file',
    'replace_in_file',
    'search_web',
    'fetch_url',
    'get_current_time',
    'list_timezones',
    'get_available_skills',
    'read_skill_detail',
    'create_task_plan',
    'get_task_status',
    'update_task_status',
    # Gateway Tools
    'gateway_call_tool',
    'gateway_query_tool',
    'gateway_tool',
    'ToolGateway',
    'get_global_gateway',
]

# Auto-discover on import
_all_tools = _auto_discover_tools()
