"""
Tools module - Re-export from tools package for backward compatibility

This module now re-exports from the tools package.
All tools are auto-discovered from the tools/ directory.
"""
# Re-export all tools from the package
from .tools import (
    get_all_tools,
    set_global_registry,
    set_global_task_manager,
    get_global_registry,
    get_global_task_manager,
    reload_tools,
)

# Re-export individual tools for backward compatibility
from .tools.system import get_system_info, execute_command
from .tools.files import read_file, write_file, list_directory, get_file_info
from .tools.network import search_web, fetch_url
from .tools.time import get_current_time, list_timezones
from .tools.skills import get_available_skills, read_skill_detail
from .tools.tasks import create_task_plan, get_task_status, update_task_status

__all__ = [
    # Functions
    'get_all_tools',
    'set_global_registry',
    'set_global_task_manager',
    'get_global_registry',
    'get_global_task_manager',
    'reload_tools',
    # Tools
    'get_system_info',
    'execute_command',
    'read_file',
    'write_file',
    'list_directory',
    'get_file_info',
    'search_web',
    'fetch_url',
    'get_current_time',
    'list_timezones',
    'get_available_skills',
    'read_skill_detail',
    'create_task_plan',
    'get_task_status',
    'update_task_status',
]
