"""
System Tools - System information and environment
"""
import platform
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool


# Get system info for tool descriptions
SYSTEM_INFO = {
    "os": platform.system(),
    "os_version": platform.version(),
    "platform": platform.platform(),
    "shell": "PowerShell" if platform.system() == "Windows" else "bash/zsh",
    "path_separator": "\\" if platform.system() == "Windows" else "/",
    "home_dir": str(Path.home()),
    "cwd": str(Path.cwd()),
}


def _get_os_hint() -> str:
    """Get OS-specific hint for tool descriptions"""
    os_name = SYSTEM_INFO["os"]
    sep = SYSTEM_INFO["path_separator"]
    shell = SYSTEM_INFO["shell"]
    return f"Current OS: {os_name} | Path separator: '{sep}' | Shell: {shell}"


@tool
def get_system_info() -> str:
    """Get current operating system and environment information"""
    return f"""Operating System: {SYSTEM_INFO['os']}
OS Version: {SYSTEM_INFO['os_version']}
Platform: {SYSTEM_INFO['platform']}
Default Shell: {SYSTEM_INFO['shell']}
Path Separator: '{SYSTEM_INFO['path_separator']}'
Home Directory: {SYSTEM_INFO['home_dir']}
Current Working Directory: {SYSTEM_INFO['cwd']}
Python Version: {platform.python_version()}

Path Format Hints:
- Windows: Use backslashes (\\) or forward slashes (/), e.g., 'C:\\Users\\name' or 'C:/Users/name'
- Linux/macOS: Use forward slashes (/), e.g., '/home/username'
- Use '~' to refer to home directory (cross-platform)
"""


@tool
def execute_command(
    command: Annotated[str, "Command to execute"],
    working_dir: Annotated[str, "Working directory (optional, uses current dir if not specified)"] = "",
    timeout: Annotated[int, "Timeout in seconds (default: 30)"] = 30
) -> str:
    """Execute a system command (use with caution)"""
    import subprocess
    import os

    try:
        # Determine working directory
        cwd = working_dir if working_dir else None
        if cwd:
            cwd = os.path.expanduser(cwd)

        # Execute command
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd
        )

        output = []
        if result.stdout:
            output.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            output.append(f"STDERR:\n{result.stderr}")

        output.append(f"Return code: {result.returncode}")

        return "\n\n".join(output)

    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {e}"
