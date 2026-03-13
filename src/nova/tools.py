"""
Tools module - Uses LangChain @tool decorator
"""
import re
import os
import sys
import httpx
import logging
import subprocess
import platform
from pathlib import Path
from typing import Annotated, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

from langchain_core.tools import tool, StructuredTool

from nova.skill import SkillRegistry

logger = logging.getLogger(__name__)

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
def search_web(query: Annotated[str, "Search query"]) -> str:
    """Search the web for information using DuckDuckGo"""
    try:
        # Use ddgs (new package name) with retries and timeout
        from ddgs import DDGS
        
        with DDGS(timeout=5) as ddgs:
            results = list(ddgs.text(query, max_results=5))
            
            if not results:
                return "No search results found"
            
            formatted_results = []
            for i, r in enumerate(results, 1):
                title = r.get('title', 'No title')
                href = r.get('href', 'No URL')
                body = r.get('body', 'No description')
                formatted_results.append(f"{i}. {title}\n   URL: {href}\n   {body}")
            
            return "\n\n".join(formatted_results)
            
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"Search failed: {e}"


@tool
def fetch_url(url: Annotated[str, "Webpage URL"]) -> str:
    """Fetch content from a URL"""
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            
            html = response.text
            
            # Clean HTML
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text[:5000]
            
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        return f"Fetch failed: {e}"


@tool
def read_file(path: Annotated[str, f"File path. {_get_os_hint()}"]) -> str:
    """Read local file content (cross-platform). Supports ~ for home directory."""
    try:
        file_path = Path(path).expanduser().resolve()
        
        if not file_path.exists():
            return f"File does not exist: {file_path}"
        
        if not file_path.is_file():
            return f"Not a file: {file_path}"
        
        # Check file size (limit to 1MB for safety)
        file_size = file_path.stat().st_size
        if file_size > 1024 * 1024:
            return f"File too large ({file_size} bytes). Max size: 1MB"
        
        content = file_path.read_text(encoding='utf-8')
        
        # Return first 10000 chars with note if truncated
        if len(content) > 10000:
            return content[:10000] + f"\n\n[...truncated, total {len(content)} characters]"
        
        return content
        
    except UnicodeDecodeError:
        # Try reading as binary and show hex dump for binary files
        try:
            binary_content = file_path.read_bytes()[:500]
            hex_preview = binary_content.hex()[:200]
            return f"Binary file detected. Hex preview: {hex_preview}..."
        except Exception as e:
            return f"Cannot read file (binary or encoding issue): {e}"
    except Exception as e:
        logger.error(f"Read file failed: {e}")
        return f"Read failed: {e}"


@tool  
def write_file(
    path: Annotated[str, f"File path. {_get_os_hint()}"], 
    content: Annotated[str, "File content"]
) -> str:
    """Write content to local file (cross-platform). Creates parent directories if needed."""
    try:
        file_path = Path(path).expanduser().resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        logger.info(f"Wrote file: {file_path}")
        return f"Successfully wrote: {file_path} ({len(content)} chars)"
        
    except Exception as e:
        logger.error(f"Write file failed: {e}")
        return f"Write failed: {e}"


@tool
def list_directory(
    path: Annotated[str, f"Directory path. {_get_os_hint()}"] = "."
) -> str:
    """List directory contents with file sizes and modification times (cross-platform)"""
    try:
        dir_path = Path(path).expanduser().resolve()
        
        if not dir_path.exists():
            return f"Directory does not exist: {dir_path}"
        
        if not dir_path.is_dir():
            return f"Not a directory: {dir_path}"
        
        items = []
        items.append(f"Directory: {dir_path}")
        items.append("-" * 60)
        
        # Separate dirs and files
        dirs = []
        files = []
        
        for item in dir_path.iterdir():
            try:
                stat = item.stat()
                size = stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                
                if item.is_dir():
                    dirs.append((item.name, "DIR", "-", mtime))
                else:
                    # Format size
                    if size < 1024:
                        size_str = f"{size}B"
                    elif size < 1024 * 1024:
                        size_str = f"{size/1024:.1f}KB"
                    else:
                        size_str = f"{size/(1024*1024):.1f}MB"
                    files.append((item.name, "FILE", size_str, mtime))
            except (OSError, PermissionError):
                # Handle permission errors
                if item.is_dir():
                    dirs.append((item.name, "DIR", "?", "?"))
                else:
                    files.append((item.name, "FILE", "?", "?"))
        
        # Sort and format
        dirs.sort(key=lambda x: x[0].lower())
        files.sort(key=lambda x: x[0].lower())
        
        for name, type_, size, mtime in dirs:
            items.append(f"[{type_:4}] {mtime:16} {size:>10}  {name}/")
        
        for name, type_, size, mtime in files:
            items.append(f"[{type_:4}] {mtime:16} {size:>10}  {name}")
        
        if not dirs and not files:
            items.append("(empty directory)")
        else:
            items.append("-" * 60)
            items.append(f"Total: {len(dirs)} directories, {len(files)} files")
        
        return "\n".join(items)
        
    except PermissionError:
        return f"Permission denied: {dir_path}"
    except Exception as e:
        logger.error(f"List directory failed: {e}")
        return f"List failed: {e}"


def _execute_command_impl(
    command: str,
    working_dir: Optional[str] = None,
    timeout: int = 60
) -> str:
    """Internal implementation of command execution"""
    try:
        # Determine shell based on OS
        if SYSTEM_INFO["os"] == "Windows":
            shell = True
            executable = None
        else:
            shell = True
            executable = "/bin/bash"
        
        # Resolve working directory
        if working_dir:
            cwd = Path(working_dir).expanduser().resolve()
            if not cwd.exists():
                return f"Working directory does not exist: {cwd}"
            if not cwd.is_dir():
                return f"Working directory is not a directory: {cwd}"
        else:
            cwd = Path.cwd()
        
        logger.info(f"Executing command: {command} in {cwd}")
        
        # Execute command
        result = subprocess.run(
            command,
            shell=shell,
            executable=executable,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )
        
        # Build output
        output_parts = []
        output_parts.append(f"Command: {command}")
        output_parts.append(f"Working Directory: {cwd}")
        output_parts.append(f"Exit Code: {result.returncode}")
        output_parts.append("-" * 40)
        
        if result.stdout:
            output_parts.append("STDOUT:")
            output_parts.append(result.stdout[:10000])  # Limit output
            if len(result.stdout) > 10000:
                output_parts.append("\n[...stdout truncated...]")
        
        if result.stderr:
            output_parts.append("\nSTDERR:")
            output_parts.append(result.stderr[:5000])  # Limit stderr
            if len(result.stderr) > 5000:
                output_parts.append("\n[...stderr truncated...]")
        
        if not result.stdout and not result.stderr:
            output_parts.append("(no output)")
        
        return "\n".join(output_parts)
        
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds"
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        return f"Command execution failed: {e}"


def _create_execute_command_tool() -> StructuredTool:
    """Create execute_command tool with dynamic system info in description"""
    os_hint = _get_os_hint()
    
    return StructuredTool.from_function(
        func=_execute_command_impl,
        name="execute_command",
        description=f"""Execute a shell command and return output. 
        
Current Environment: {os_hint}

WARNING: Be careful with destructive commands! This tool executes commands directly on the system.
- On Windows: Commands run in cmd/PowerShell
- On Linux/macOS: Commands run in bash
- Use 'working_dir' parameter to specify where to run the command
- Use 'timeout' parameter to prevent long-running commands (default: 60s)

Examples:
- Windows: dir, echo %PATH%, type file.txt
- Linux/macOS: ls, echo $PATH, cat file.txt
""",
        return_direct=False,
    )


@tool
def get_current_time(
    timezone: Annotated[Optional[str], "Timezone (e.g., 'America/New_York', 'Asia/Shanghai', 'UTC'). Uses system timezone if not specified."] = None
) -> str:
    """Get current date and time for a specific timezone"""
    try:
        if timezone:
            if timezone not in available_timezones():
                # Try to find similar timezones
                available = [tz for tz in available_timezones() if timezone.lower() in tz.lower()]
                if available:
                    suggestions = ", ".join(available[:5])
                    return f"Timezone '{timezone}' not found. Did you mean: {suggestions}?"
                return f"Timezone '{timezone}' not found. Use format like 'America/New_York', 'Asia/Shanghai', 'Europe/London', 'UTC'"
            tz = ZoneInfo(timezone)
        else:
            # Use system local timezone
            tz = datetime.now().astimezone().tzinfo
        
        now = datetime.now(tz)
        
        # Format the output
        formatted = now.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")
        weekday = now.strftime("%A")
        
        return f"Current time: {formatted}\nDay: {weekday}\nTimezone: {tz}"
        
    except Exception as e:
        logger.error(f"Get time failed: {e}")
        return f"Failed to get time: {e}"


@tool
def list_timezones(
    region: Annotated[Optional[str], "Filter by region (e.g., 'America', 'Asia', 'Europe'). Lists all if not specified."] = None
) -> str:
    """List available timezones, optionally filtered by region"""
    try:
        timezones = available_timezones()
        
        if region:
            filtered = [tz for tz in timezones if tz.lower().startswith(region.lower())]
            if not filtered:
                return f"No timezones found for region '{region}'"
            result = filtered[:30]  # Limit results
            more = len(filtered) - 30 if len(filtered) > 30 else 0
            output = "\n".join(result)
            if more > 0:
                output += f"\n... and {more} more"
            return f"Timezones in {region}:\n{output}"
        else:
            # Return common timezones
            common = [
                "UTC",
                "America/New_York",
                "America/Los_Angeles",
                "America/Chicago",
                "America/Denver",
                "America/Toronto",
                "America/Sao_Paulo",
                "Europe/London",
                "Europe/Paris",
                "Europe/Berlin",
                "Europe/Moscow",
                "Asia/Tokyo",
                "Asia/Shanghai",
                "Asia/Hong_Kong",
                "Asia/Singapore",
                "Asia/Seoul",
                "Asia/Dubai",
                "Asia/Kolkata",
                "Australia/Sydney",
                "Australia/Melbourne",
                "Pacific/Auckland",
            ]
            return "Common timezones:\n" + "\n".join(common) + "\n\nUse list_timezones with region parameter to see more (e.g., 'America', 'Asia', 'Europe')"
        
    except Exception as e:
        logger.error(f"List timezones failed: {e}")
        return f"Failed to list timezones: {e}"


def get_all_tools(registry: SkillRegistry = None):
    """Get all tools"""
    # Create execute_command tool dynamically with system info
    execute_command_tool = _create_execute_command_tool()
    
    base_tools = [
        get_system_info,
        search_web, 
        fetch_url, 
        read_file, 
        write_file, 
        list_directory,
        execute_command_tool,
        get_current_time,
        list_timezones,
    ]
    
    if registry:
        # Dynamically create tool functions bound to registry
        @tool
        def get_available_skills() -> str:
            """Get list of all available skills"""
            skills = registry.list_all()
            if not skills:
                return "No skills available"
            
            result = []
            for skill in skills:
                result.append(f"- {skill.name}: {skill.description[:50]}...")
            
            return "Available Skills:\n" + "\n".join(result)
        
        @tool
        def read_skill_detail(skill_name: Annotated[str, "Skill name"]) -> str:
            """Read detailed content of a specific skill"""
            return registry.read_skill_content(skill_name)
        
        skill_tools = [get_available_skills, read_skill_detail]
        return base_tools + skill_tools
    
    return base_tools
