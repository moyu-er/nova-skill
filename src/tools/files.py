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


def _edit_file_unix(file_path: Path, start_line: int, end_line: int, new_content: str) -> str:
    """
    Unix/Linux/macOS implementation using sed for lightweight line editing.
    Falls back to Python implementation if sed fails.
    
    sed command reference:
    - 'Nd' : Delete line N
    - 'N,Md' : Delete lines N to M
    - 'Nc\text' : Replace line N with text
    - 'N,Mc\text' : Replace lines N to M with text
    - 'Ni\text' : Insert text before line N
    """
    import subprocess
    import tempfile
    import os
    import shlex
    
    # First, get total line count using wc -l (very fast)
    try:
        result = subprocess.run(
            ['wc', '-l', str(file_path)],
            capture_output=True,
            text=True,
            timeout=5
        )
        total_lines = int(result.stdout.strip().split()[0])
    except:
        # Fallback to Python
        return _edit_file_python(file_path, start_line, end_line, new_content)
    
    # Handle append case
    if start_line > total_lines:
        with open(file_path, 'a', encoding='utf-8') as f:
            # Check if file ends with newline
            with open(file_path, 'rb') as fb:
                fb.seek(0, 2)  # Seek to end
                if fb.tell() > 0:
                    fb.seek(-1, 1)
                    if fb.read(1) != b'\n':
                        f.write('\n')
            f.write(new_content)
        return f"Appended content to {file_path} (after line {total_lines})"
    
    # Use sed for line replacement/deletion/insertion
    try:
        # Create temp file for atomic operation
        fd, temp_path = tempfile.mkstemp(dir=file_path.parent, suffix='.tmp')
        os.close(fd)
        temp_file = Path(temp_path)
        
        # Build sed script file for complex multi-line operations
        # This is more reliable than inline commands for multi-line content
        sed_script_lines = []
        
        if not new_content:
            # Delete mode: delete lines start_line to end_line
            if start_line == end_line:
                sed_script_lines.append(f"{start_line}d")
            else:
                sed_script_lines.append(f"{start_line},{end_line}d")
        else:
            # Replace mode: replace lines start_line to end_line with new_content
            # sed 'c' command replaces the addressed line(s) with new text
            new_lines = new_content.split('\n')
            
            # For multi-line replacement with 'c' command, we need to use
            # backslash-escaped newlines in the replacement text
            if len(new_lines) == 1:
                # Single line replacement - simple case
                escaped_content = new_lines[0].replace('\\', '\\\\').replace('/', '\\/').replace('&', '\\&')
                if start_line == end_line:
                    sed_script_lines.append(f"{start_line}c\\")
                    sed_script_lines.append(escaped_content)
                else:
                    sed_script_lines.append(f"{start_line},{end_line}c\\")
                    sed_script_lines.append(escaped_content)
            else:
                # Multi-line replacement
                # Use the 'c' command with escaped newlines
                if start_line == end_line:
                    sed_script_lines.append(f"{start_line}c\\")
                else:
                    sed_script_lines.append(f"{start_line},{end_line}c\\")
                
                # Add each line except the last with backslash continuation
                for i, line in enumerate(new_lines[:-1]):
                    escaped_line = line.replace('\\', '\\\\').replace('/', '\\/').replace('&', '\\&')
                    sed_script_lines.append(escaped_line + "\\")
                
                # Last line without backslash
                escaped_last = new_lines[-1].replace('\\', '\\\\').replace('/', '\\/').replace('&', '\\&')
                sed_script_lines.append(escaped_last)
        
        # Write sed script to temp file
        sed_script_path = temp_file.with_suffix('.sed')
        with open(sed_script_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(sed_script_lines))
        
        try:
            # Run sed with script file
            with open(temp_file, 'w', encoding='utf-8') as out_f:
                subprocess.run(
                    ['sed', '-f', str(sed_script_path), str(file_path)],
                    stdout=out_f,
                    check=True,
                    timeout=30
                )
            
            # Atomic replace
            temp_file.replace(file_path)
            
        finally:
            # Clean up sed script
            if sed_script_path.exists():
                sed_script_path.unlink()
        
        # Calculate stats for return message
        replaced_count = end_line - start_line + 1
        inserted_count = len(new_content.split('\n')) if new_content else 0
        
        if not new_content:
            return f"Successfully deleted lines {start_line}-{end_line} in {file_path}"
        else:
            return f"Successfully replaced lines {start_line}-{end_line} with {inserted_count} line(s) in {file_path}"
            
    except Exception as e:
        # Clean up temp files if exist
        if 'temp_file' in locals() and temp_file.exists():
            temp_file.unlink()
        if 'sed_script_path' in locals() and sed_script_path.exists():
            sed_script_path.unlink()
        # Fallback to Python implementation
        return _edit_file_python(file_path, start_line, end_line, new_content)


def _edit_file_windows(file_path: Path, start_line: int, end_line: int, new_content: str) -> str:
    """
    Windows implementation using PowerShell for efficient line editing.
    Falls back to Python implementation if PowerShell fails.
    """
    import subprocess
    import tempfile
    import os
    
    try:
        # Get line count using PowerShell (fast)
        ps_cmd = f"(Get-Content -Path '{file_path}' -ErrorAction Stop).Count"
        result = subprocess.run(
            ['powershell', '-Command', ps_cmd],
            capture_output=True,
            text=True,
            timeout=5
        )
        total_lines = int(result.stdout.strip()) if result.stdout.strip() else 0
    except:
        # Fallback to Python
        return _edit_file_python(file_path, start_line, end_line, new_content)
    
    # Handle append case
    if start_line > total_lines:
        with open(file_path, 'a', encoding='utf-8') as f:
            with open(file_path, 'rb') as fb:
                fb.seek(0, 2)
                if fb.tell() > 0:
                    fb.seek(-1, 1)
                    if fb.read(1) != b'\n':
                        f.write('\n')
            f.write(new_content)
        return f"Appended content to {file_path} (after line {total_lines})"
    
    try:
        # Create temp file
        fd, temp_path = tempfile.mkstemp(dir=file_path.parent, suffix='.tmp')
        os.close(fd)
        temp_file = Path(temp_path)
        
        # Build PowerShell command
        new_content_escaped = new_content.replace("'", "''")
        
        if start_line == end_line and new_content:
            # Insert mode
            ps_cmd = f"""
            $lines = Get-Content -Path '{file_path}'
            $newLines = @('{new_content_escaped.replace(chr(10), "', '")}')
            $before = $lines[0..{start_line-2}]
            $after = $lines[{start_line-1}..($lines.Count-1)]
            $result = $before + $newLines + $after
            $result | Set-Content -Path '{temp_file}'
            """
        elif not new_content:
            # Delete mode
            ps_cmd = f"""
            $lines = Get-Content -Path '{file_path}'
            $before = $lines[0..{start_line-2}]
            $after = $lines[{end_line}..($lines.Count-1)]
            $result = $before + $after
            $result | Set-Content -Path '{temp_file}'
            """
        else:
            # Replace mode
            ps_cmd = f"""
            $lines = Get-Content -Path '{file_path}'
            $newLines = @('{new_content_escaped.replace(chr(10), "', '")}')
            $before = $lines[0..{start_line-2}]
            $after = $lines[{end_line}..($lines.Count-1)]
            $result = $before + $newLines + $after
            $result | Set-Content -Path '{temp_file}'
            """
        
        subprocess.run(
            ['powershell', '-Command', ps_cmd],
            check=True,
            timeout=30
        )
        
        # Atomic replace
        temp_file.replace(file_path)
        
        replaced_count = end_line - start_line + 1
        inserted_count = len(new_content.split('\n')) if new_content else 0
        
        if replaced_count == 0 and inserted_count > 0:
            return f"Successfully inserted {inserted_count} line(s) at line {start_line} in {file_path}"
        elif replaced_count > 0 and inserted_count == 0:
            return f"Successfully deleted lines {start_line}-{end_line} in {file_path}"
        else:
            return f"Successfully replaced lines {start_line}-{end_line} with {inserted_count} line(s) in {file_path}"
            
    except Exception as e:
        if 'temp_file' in locals() and temp_file.exists():
            temp_file.unlink()
        return _edit_file_python(file_path, start_line, end_line, new_content)


def _edit_file_python(file_path: Path, start_line: int, end_line: int, new_content: str) -> str:
    """
    Pure Python implementation as fallback.
    Memory-efficient for most files.
    """
    # Read file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Handle empty file
    if not content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return f"Created content in {file_path} (file was empty)"
    
    # Split into lines, preserving whether file ends with newline
    ends_with_newline = content.endswith('\n')
    all_lines = content.split('\n')
    # Remove empty string at end if file ends with newline
    if ends_with_newline and all_lines[-1] == '':
        all_lines.pop()
    
    total_lines = len(all_lines)
    
    # Handle append
    if start_line > total_lines:
        with open(file_path, 'a', encoding='utf-8') as f:
            if total_lines > 0:
                f.write('\n')
            f.write(new_content)
        return f"Appended content to {file_path} (after line {total_lines})"
    
    # Perform edit
    start_idx = start_line - 1
    end_idx = min(end_line, total_lines)
    new_lines = new_content.split('\n') if new_content else []
    
    result_lines = all_lines[:start_idx] + new_lines + all_lines[end_idx:]
    
    # Write back, preserving original newline behavior
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result_lines))
        # Add trailing newline if original file had one
        if ends_with_newline:
            f.write('\n')
    
    replaced_count = end_idx - start_idx
    inserted_count = len(new_lines)
    
    if replaced_count == 0 and inserted_count > 0:
        return f"Successfully inserted {inserted_count} line(s) at line {start_line} in {file_path}"
    elif replaced_count > 0 and inserted_count == 0:
        return f"Successfully deleted lines {start_line}-{end_line} in {file_path}"
    else:
        return f"Successfully replaced lines {start_line}-{end_line} with {inserted_count} line(s) in {file_path}"


@tool
def edit_file(
    path: Annotated[str, f"File path. {_get_os_hint()}"],
    start_line: Annotated[int, "Start line number to replace (1-based, inclusive)"],
    end_line: Annotated[int, "End line number to replace (1-based, inclusive). Use same as start_line to insert at that position."],
    new_content: Annotated[str, "New content to replace the specified lines. Can contain newlines for multi-line replacement."]
) -> str:
    """
    Precisely edit a file by replacing specific line range (lightweight, OS-optimized implementation).
    
    Uses native OS tools when available (sed on Unix, PowerShell on Windows) for efficiency,
    with pure Python fallback for maximum compatibility.
    
    Use this for targeted modifications when you know the line numbers.
    For inserting lines, set start_line = end_line (inserts before that line).
    For appending, use a line number beyond the current line count.
    
    Examples:
        - Replace lines 10-15: start_line=10, end_line=15, new_content="new lines"
        - Insert at line 5: start_line=5, end_line=5, new_content="inserted line"
        - Delete lines 3-5: start_line=3, end_line=5, new_content=""
    """
    try:
        file_path = Path(path).expanduser().resolve()
        
        if not file_path.exists():
            return f"File not found: {path}"
        
        if not file_path.is_file():
            return f"Path is not a file: {path}"
        
        # Validate line numbers
        if start_line < 1:
            return f"start_line must be >= 1, got {start_line}"
        if end_line < start_line:
            return f"end_line ({end_line}) must be >= start_line ({start_line})"
        
        # Route to OS-specific implementation
        if os.name == 'nt':  # Windows
            return _edit_file_windows(file_path, start_line, end_line, new_content)
        else:  # Unix/Linux/macOS
            return _edit_file_unix(file_path, start_line, end_line, new_content)
            
    except Exception as e:
        return f"Error editing file: {e}"


@tool
def replace_in_file(
    path: Annotated[str, f"File path. {_get_os_hint()}"],
    old_string: Annotated[str, "The exact string to search for. Must match exactly including whitespace."],
    new_string: Annotated[str, "The replacement string. Can contain newlines."],
    count: Annotated[int, "Maximum number of replacements to make. Default 0 means replace all occurrences."] = 0
) -> str:
    """
    Replace specific content in a file by exact string matching (lightweight search & replace).
    
    Use this when you know the exact content to replace but not the line numbers.
    The old_string must match exactly including whitespace and newlines.
    
    Examples:
        - Replace all: old_string="foo", new_string="bar"
        - Replace first 2: old_string="foo", new_string="bar", count=2
        - Replace multi-line: old_string="line1\nline2", new_string="new1\nnew2"
    """
    try:
        file_path = Path(path).expanduser().resolve()
        
        if not file_path.exists():
            return f"File not found: {path}"
        
        if not file_path.is_file():
            return f"Path is not a file: {path}"
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if old_string exists
        if old_string not in content:
            return f"String not found in file: {old_string[:50]}..."
        
        # Perform replacement
        if count == 0:
            # Replace all
            new_content = content.replace(old_string, new_string)
            replaced_count = content.count(old_string)
        else:
            # Replace limited count
            new_content = content.replace(old_string, new_string, count)
            replaced_count = min(count, content.count(old_string))
        
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        if replaced_count == 1:
            return f"Successfully replaced 1 occurrence in {path}"
        else:
            return f"Successfully replaced {replaced_count} occurrences in {path}"
            
    except Exception as e:
        return f"Error replacing in file: {e}"
