"""
File Tools - File system operations
"""
import os
import mmap
from pathlib import Path
from typing import Annotated, Optional, List, Tuple
from datetime import datetime
from contextlib import contextmanager

from langchain_core.tools import tool

from .system import _get_os_hint

# Maximum lines per read operation
MAX_LINES_PER_READ = 300


@contextmanager
def safe_mmap(file_path: Path):
    """
    安全地创建内存映射，处理文件被修改或删除的情况
    """
    fd = None
    mm = None
    try:
        # 以读写模式打开文件（mmap需要）
        fd = os.open(str(file_path), os.O_RDWR)
        
        # 获取文件大小
        file_size = os.fstat(fd).st_size
        
        if file_size == 0:
            yield None, 0
            return
        
        # 创建内存映射
        mm = mmap.mmap(fd, file_size, access=mmap.ACCESS_READ)
        yield mm, file_size
        
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except PermissionError:
        raise PermissionError(f"Permission denied: {file_path}")
    except OSError as e:
        # 文件被修改或删除时的处理
        raise OSError(f"File access error (may be modified or deleted): {e}")
    finally:
        if mm is not None:
            try:
                mm.close()
            except:
                pass
        if fd is not None:
            try:
                os.close(fd)
            except:
                pass


def count_lines_mmap(mm: mmap.mmap) -> int:
    """
    使用 mmap 快速计算总行数
    """
    if mm is None:
        return 0
    
    count = 0
    pos = 0
    
    while True:
        pos = mm.find(b'\n', pos)
        if pos == -1:
            break
        count += 1
        pos += 1
    
    # 如果文件不以换行符结尾，最后一行也需要计数
    if mm.size() > 0 and mm[-1:] != b'\n':
        count += 1
    
    return count


def read_lines_mmap(
    mm: mmap.mmap, 
    start_line: int, 
    max_lines: int,
    total_lines: int
) -> Tuple[List[str], int, int]:
    """
    使用 mmap 从指定行开始读取
    
    Args:
        mm: mmap 对象
        start_line: 起始行号（0-based）
        max_lines: 最大读取行数
        total_lines: 总行数（用于边界检查）
    
    Returns:
        (lines, actual_start, actual_end)
    """
    if mm is None or start_line >= total_lines:
        return [], start_line, start_line
    
    lines = []
    current_line = 0
    pos = 0
    
    # 快速跳到起始行
    while current_line < start_line and pos < mm.size():
        new_pos = mm.find(b'\n', pos)
        if new_pos == -1:
            break
        pos = new_pos + 1
        current_line += 1
    
    # 读取指定行数
    line_count = 0
    actual_start = start_line
    actual_end = start_line
    
    while line_count < max_lines and pos < mm.size():
        # 找到行尾
        end_pos = mm.find(b'\n', pos)
        if end_pos == -1:
            end_pos = mm.size()
        
        # 解码行内容（处理可能的编码错误）
        try:
            line = mm[pos:end_pos].decode('utf-8')
        except UnicodeDecodeError:
            # 尝试其他编码或使用替换模式
            line = mm[pos:end_pos].decode('utf-8', errors='replace')
        
        lines.append(line.rstrip('\r'))
        line_count += 1
        actual_end = start_line + line_count
        
        # 移动到下一行
        if end_pos < mm.size():
            pos = end_pos + 1
        else:
            break
    
    return lines, actual_start, actual_end


@tool
def read_file(
    path: Annotated[str, f"File path. {_get_os_hint()}"],
    start_line: Annotated[Optional[int], "Start line number (1-based, inclusive). If not specified, starts from line 1."] = None,
    end_line: Annotated[Optional[int], "End line number (inclusive). If not specified, reads up to 300 lines from start."] = None
) -> str:
    """
    Read local file content with line range support (cross-platform).
    Supports ~ for home directory.

    Reads up to 300 lines per call. For larger files, use multiple calls with start_line/end_line.
    Uses memory-mapped I/O for efficient random access.
    """
    try:
        file_path = Path(path).expanduser().resolve()

        if not file_path.exists():
            return f"File not found: {path}"

        if not file_path.is_file():
            return f"Path is not a file: {path}"

        # 使用 mmap 安全地读取文件
        try:
            with safe_mmap(file_path) as (mm, file_size):
                if mm is None:
                    return f"File is empty: {path}"
                
                # 计算总行数
                total_lines = count_lines_mmap(mm)
                
                # 规范化行号（1-based to 0-based）
                start = (start_line - 1) if start_line is not None and start_line > 0 else 0
                max_lines = MAX_LINES_PER_READ
                
                # 如果 end_line 被指定，计算 max_lines
                if end_line is not None:
                    if end_line < start + 1:
                        return f"Invalid range: end_line ({end_line}) must be >= start_line ({start_line or 1})"
                    max_lines = min(end_line - start, MAX_LINES_PER_READ)
                
                # 检查起始行是否超出范围
                if start >= total_lines:
                    return f"File has only {total_lines} lines. Cannot read from line {start + 1}."
                
                # 使用 mmap 读取指定行
                lines, actual_start, actual_end = read_lines_mmap(mm, start, max_lines, total_lines)
                
                # 构建结果
                result_lines = []
                
                # 添加头部信息
                result_lines.append(f"[Lines {actual_start + 1}-{actual_end} of {total_lines}]\n")
                
                # 添加行号到内容
                for i, line in enumerate(lines, start=actual_start + 1):
                    result_lines.append(f"{i:4d}| {line}")
                
                # 如果有更多行，添加提示
                if actual_end < total_lines:
                    result_lines.append(f"\n[... {total_lines - actual_end} more lines. Use start_line={actual_end + 1} to continue reading ...]")
                
                return '\n'.join(result_lines)
                
        except FileNotFoundError:
            return f"File not found (may have been deleted): {path}"
        except PermissionError:
            return f"Permission denied: {path}"
        except OSError as e:
            return f"File access error (may be modified or locked): {e}"

    except UnicodeDecodeError:
        return f"File appears to be binary: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def write_file(
    path: Annotated[str, f"File path. {_get_os_hint()}"],
    content: Annotated[str, "File content to write"]
) -> str:
    """
    Write content to a file (cross-platform).
    Supports ~ for home directory.
    Creates parent directories if they don't exist.
    """
    try:
        file_path = Path(path).expanduser().resolve()

        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool
def list_directory(
    path: Annotated[str, f"Directory path. {_get_os_hint()}"] = "."
) -> str:
    """
    List directory contents (cross-platform).
    Supports ~ for home directory.
    """
    try:
        dir_path = Path(path).expanduser().resolve()

        if not dir_path.exists():
            return f"Directory not found: {path}"

        if not dir_path.is_dir():
            return f"Path is not a directory: {path}"

        items = []
        for item in sorted(dir_path.iterdir()):
            item_type = "📁" if item.is_dir() else "📄"
            items.append(f"{item_type} {item.name}")

        if not items:
            return f"Directory is empty: {path}"

        return f"Contents of {path}:\n" + "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {e}"


@tool
def get_file_info(
    path: Annotated[str, f"File path. {_get_os_hint()}"]
) -> str:
    """
    Get file information (size, modification time, etc.).
    Supports ~ for home directory.
    """
    try:
        file_path = Path(path).expanduser().resolve()

        if not file_path.exists():
            return f"File not found: {path}"

        stat = file_path.stat()
        size = stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')

        # Format size
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / (1024 * 1024):.1f} MB"

        info = [
            f"File: {path}",
            f"Size: {size_str}",
            f"Modified: {mtime}",
            f"Type: {'Directory' if file_path.is_dir() else 'File'}"
        ]

        return "\n".join(info)
    except Exception as e:
        return f"Error getting file info: {e}"
