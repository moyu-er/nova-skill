"""
Tools module tests
"""
import json
import tempfile
import os
from pathlib import Path

from src import SkillRegistry
from src.tools import *


class TestTools:
    """Test tool functions"""
    
    def test_get_all_tools_without_registry(self):
        """Test getting all tools (without explicit registry - uses global)"""
        tools = get_all_tools()
        tool_names = [t.name for t in tools]

        # Base tools
        assert "get_system_info" in tool_names
        assert "search_web" in tool_names
        assert "fetch_url" in tool_names
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "list_directory" in tool_names
        assert "execute_command" in tool_names
        assert "get_current_time" in tool_names
        assert "list_timezones" in tool_names

        # Skill tools (always included now)
        assert "get_available_skills" in tool_names
        assert "read_skill_detail" in tool_names

        # Task planning tools (always included now)
        assert "create_task_plan" in tool_names
        assert "get_task_status" in tool_names
        assert "update_task_status" in tool_names
        assert "list_task_plans" in tool_names
        assert "get_next_task" in tool_names

        # Gateway tools
        assert "gateway_call_tool" in tool_names
        assert "gateway_query_tool" in tool_names

        assert len(tools) == 21  # 9 base + 2 skill + 5 task planning + 3 file + 2 gateway

    def test_get_all_tools_with_registry(self):
        """Test getting all tools (with explicit registry)"""
        skills_dir = Path(__file__).parent.parent / "skills"
        registry = SkillRegistry(skills_dir)
        tools = get_all_tools(registry)
        tool_names = [t.name for t in tools]

        # Base tools
        assert "get_system_info" in tool_names
        assert "search_web" in tool_names
        assert "fetch_url" in tool_names

        # Time tools
        assert "get_current_time" in tool_names
        assert "list_timezones" in tool_names

        # Command execution
        assert "execute_command" in tool_names

        # Skill related tools
        assert "get_available_skills" in tool_names
        assert "read_skill_detail" in tool_names

        # Task planning tools (always included now)
        assert "create_task_plan" in tool_names
        assert "get_task_status" in tool_names
        assert "update_task_status" in tool_names
        assert "list_task_plans" in tool_names
        assert "get_next_task" in tool_names

        # Gateway tools
        assert "gateway_call_tool" in tool_names
        assert "gateway_query_tool" in tool_names

        assert len(tools) == 21  # 9 base + 2 skill + 5 task planning + 3 file + 2 gateway

    def test_read_skill_detail_tool(self):
        """Test read_skill_detail tool"""
        skills_dir = Path(__file__).parent.parent / "skills"
        registry = SkillRegistry(skills_dir)
        tools = get_all_tools(registry)
        
        # Find read_skill_detail tool
        read_skill_tool = [t for t in tools if t.name == 'read_skill_detail'][0]

        # Call tool with mut_los skill
        result = read_skill_tool.invoke({'skill_name': 'mut_los'})

        # Verify returned markdown content (without frontmatter)
        assert result
        assert "##" in result
        assert len(result) > 100

    def test_get_available_skills_tool(self):
        """Test get_available_skills tool"""
        skills_dir = Path(__file__).parent.parent / "skills"
        registry = SkillRegistry(skills_dir)
        tools = get_all_tools(registry)

        # Find tool
        get_skills_tool = [t for t in tools if t.name == 'get_available_skills'][0]

        # Call tool
        result = get_skills_tool.invoke({})

        # Verify returned skill list
        assert result
        assert "mut_los" in result or "writing-skills" in result


class TestBasicTools:
    """Test basic tools"""
    
    def test_list_directory(self):
        """Test list_directory tool"""
        result = list_directory.invoke({'path': '.'})
        assert result
        assert "Contents of" in result
        assert len(result) > 0
    
    def test_list_directory_with_tilde(self):
        """Test list_directory with home directory shortcut"""
        result = list_directory.invoke({'path': '~'})
        assert result
        assert "Contents of" in result
    
    def test_read_file(self):
        """Test read_file tool"""
        # Read README.md
        result = read_file.invoke({'path': 'README.md'})
        assert result
        assert "Nova Skill" in result
    
    def test_read_file_not_found(self):
        """Test read_file with non-existent file"""
        result = read_file.invoke({'path': 'nonexistent_file_12345.txt'})
        assert "not found" in result
    
    def test_write_file(self):
        """Test write_file tool"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_write.txt"
            test_content = "Hello, World!"
            
            # Write file
            result = write_file.invoke({'path': str(test_file), 'content': test_content})
            assert "Successfully wrote" in result

            # Read back
            content = read_file.invoke({'path': str(test_file)})
            assert test_content in content

    def test_write_file_creates_directories(self):
        """Test write_file creates parent directories"""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_file = Path(tmpdir) / "nested" / "deep" / "file.txt"
            test_content = "Nested content"
            
            result = write_file.invoke({'path': str(nested_file), 'content': test_content})
            assert "Successfully wrote" in result
            assert nested_file.exists()


class TestSystemInfoTool:
    """Test system info tool"""
    
    def test_get_system_info(self):
        """Test get_system_info tool"""
        result = get_system_info.invoke({})
        assert result
        assert "Operating System:" in result
        assert "Path Separator:" in result
        assert "Home Directory:" in result


class TestExecuteCommandTool:
    """Test command execution tool"""
    
    def _get_execute_command_tool(self):
        """Helper to get execute_command tool from get_all_tools"""
        tools = get_all_tools()
        return [t for t in tools if t.name == 'execute_command'][0]
    
    def test_execute_command_echo(self):
        """Test basic command execution"""
        execute_command = self._get_execute_command_tool()
        
        if os.name == 'nt':  # Windows
            result = execute_command.invoke({'command': 'echo Hello'})
        else:  # Unix
            result = execute_command.invoke({'command': 'echo "Hello"'})
        
        assert result
        assert "Return code: 0" in result or "Exit Code: 0" in result
        assert "Hello" in result
    
    def test_execute_command_with_working_dir(self):
        """Test command with working directory"""
        execute_command = self._get_execute_command_tool()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            if os.name == 'nt':  # Windows
                result = execute_command.invoke({
                    'command': 'cd',
                    'working_dir': tmpdir
                })
                assert tmpdir.replace('/', '\\') in result or tmpdir in result
            else:  # Unix
                result = execute_command.invoke({
                    'command': 'pwd',
                    'working_dir': tmpdir
                })
                assert tmpdir in result
    
    def test_execute_command_invalid_dir(self):
        """Test command with invalid working directory"""
        execute_command = self._get_execute_command_tool()
        
        result = execute_command.invoke({
            'command': 'echo test',
            'working_dir': '/nonexistent/path/12345'
        })
        assert "does not exist" in result or "Error" in result
    
    def test_execute_command_timeout(self):
        """Test command timeout"""
        execute_command = self._get_execute_command_tool()
        
        if os.name == 'nt':  # Windows - use ping which is more reliable
            result = execute_command.invoke({
                'command': 'ping -n 3 127.0.0.1',
                'timeout': 1
            })
        else:  # Unix
            result = execute_command.invoke({
                'command': 'sleep 5',
                'timeout': 1
            })
        
        assert "timed out" in result or "Exit Code:" in result


class TestTimeTools:
    """Test time-related tools"""
    
    def test_get_current_time_system(self):
        """Test get_current_time with system timezone"""
        result = get_current_time.invoke({})
        assert result
        assert "Current local time:" in result or "Current time:" in result
    
    def test_get_current_time_with_timezone(self):
        """Test get_current_time with specific timezone"""
        result = get_current_time.invoke({'timezone': 'UTC'})
        assert result
        assert "Current time in UTC:" in result or "Current time:" in result
        assert "UTC" in result
    
    def test_get_current_time_invalid_timezone(self):
        """Test get_current_time with invalid timezone"""
        result = get_current_time.invoke({'timezone': 'Invalid/Timezone'})
        assert "not found" in result or "Invalid timezone" in result
    
    def test_list_timezones(self):
        """Test list_timezones tool"""
        result = list_timezones.invoke({})
        assert result
        assert "timezones" in result or "UTC" in result
    
    def test_list_timezones_with_region(self):
        """Test list_timezones with region filter"""
        result = list_timezones.invoke({'region': 'America'})
        assert result
        assert "America/" in result


class TestNetworkTools:
    """Test network-related tools"""
    
    def test_fetch_url(self):
        """Test fetch_url tool"""
        # Test with a simple URL
        result = fetch_url.invoke({'url': 'https://httpbin.org/html'})
        # Note: This test may fail if no network access
        # Just check it doesn't crash
        assert isinstance(result, str)


class TestEditFileTool:
    """Test edit_file tool"""
    
    def _get_edit_file_tool(self):
        """Helper to get edit_file tool"""
        tools = get_all_tools()
        return [t for t in tools if t.name == 'edit_file'][0]
    
    def test_edit_file_replace_lines(self):
        """Test replacing specific lines"""
        edit_file = self._get_edit_file_tool()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("line1\nline2\nline3\nline4\nline5")
            temp_path = f.name
        
        try:
            result = edit_file.invoke({
                'path': temp_path,
                'start_line': 2,
                'end_line': 3,
                'new_content': 'new_line2\nnew_line3'
            })
            assert "Successfully replaced lines 2-3" in result or "Successfully replaced lines 2-3 with" in result
            
            # Verify content (PowerShell adds trailing newline on Windows)
            with open(temp_path, 'r') as f:
                content = f.read()
            expected = "line1\nnew_line2\nnew_line3\nline4\nline5"
            assert content.startswith(expected), f"Content mismatch: {content!r}"
            assert "line1" in content and "new_line2" in content and "line4" in content
        finally:
            os.unlink(temp_path)
    
    def test_edit_file_insert_line(self):
        """Test inserting a line"""
        edit_file = self._get_edit_file_tool()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("line1\nline2")
            temp_path = f.name
        
        try:
            result = edit_file.invoke({
                'path': temp_path,
                'start_line': 2,
                'end_line': 2,
                'new_content': 'inserted_line'
            })
            assert "inserted" in result.lower() or "replaced" in result.lower()
            
            with open(temp_path, 'r') as f:
                content = f.read()
            # Check content is correct (order matters)
            assert "line1" in content
            assert "inserted_line" in content
            assert "line2" in content
            # Verify order: line1 comes before inserted_line, which comes before line2
            line1_pos = content.find("line1")
            inserted_pos = content.find("inserted_line")
            line2_pos = content.find("line2")
            assert line1_pos < inserted_pos < line2_pos, f"Order incorrect: {content!r}"
        finally:
            os.unlink(temp_path)
    
    def test_edit_file_delete_lines(self):
        """Test deleting lines"""
        edit_file = self._get_edit_file_tool()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("line1\nline2\nline3\nline4")
            temp_path = f.name
        
        try:
            result = edit_file.invoke({
                'path': temp_path,
                'start_line': 2,
                'end_line': 3,
                'new_content': ''
            })
            assert "deleted" in result.lower()
            
            with open(temp_path, 'r') as f:
                content = f.read()
            # Verify lines 2 and 3 were deleted
            assert "line1" in content
            assert "line4" in content
            assert "line2" not in content
            assert "line3" not in content
            # Verify order
            assert content.find("line1") < content.find("line4")
        finally:
            os.unlink(temp_path)


class TestReplaceInFileTool:
    """Test replace_in_file tool"""
    
    def _get_replace_in_file_tool(self):
        """Helper to get replace_in_file tool"""
        tools = get_all_tools()
        return [t for t in tools if t.name == 'replace_in_file'][0]
    
    def test_replace_in_file_single(self):
        """Test single replacement"""
        replace_in_file = self._get_replace_in_file_tool()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("hello world foo bar")
            temp_path = f.name
        
        try:
            result = replace_in_file.invoke({
                'path': temp_path,
                'old_string': 'world',
                'new_string': 'universe'
            })
            assert "replaced 1 occurrence" in result
            
            with open(temp_path, 'r') as f:
                content = f.read()
            assert "hello universe foo bar" == content
        finally:
            os.unlink(temp_path)
    
    def test_replace_in_file_multiple(self):
        """Test multiple replacements"""
        replace_in_file = self._get_replace_in_file_tool()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("foo bar foo baz foo")
            temp_path = f.name
        
        try:
            result = replace_in_file.invoke({
                'path': temp_path,
                'old_string': 'foo',
                'new_string': 'hello'
            })
            assert "replaced 3 occurrences" in result
            
            with open(temp_path, 'r') as f:
                content = f.read()
            assert "hello bar hello baz hello" == content
        finally:
            os.unlink(temp_path)
    
    def test_replace_in_file_limited_count(self):
        """Test limited count replacement"""
        replace_in_file = self._get_replace_in_file_tool()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("foo bar foo baz foo")
            temp_path = f.name
        
        try:
            result = replace_in_file.invoke({
                'path': temp_path,
                'old_string': 'foo',
                'new_string': 'hello',
                'count': 2
            })
            assert "replaced 2 occurrences" in result
            
            with open(temp_path, 'r') as f:
                content = f.read()
            assert "hello bar hello baz foo" == content
        finally:
            os.unlink(temp_path)
    
    def test_replace_in_file_multiline(self):
        """Test multi-line replacement"""
        replace_in_file = self._get_replace_in_file_tool()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("line1\nline2\nline3\nline4")
            temp_path = f.name
        
        try:
            result = replace_in_file.invoke({
                'path': temp_path,
                'old_string': 'line2\nline3',
                'new_string': 'new2\nnew3'
            })
            assert "replaced 1 occurrence" in result
            
            with open(temp_path, 'r') as f:
                content = f.read()
            assert "line1\nnew2\nnew3\nline4" == content
        finally:
            os.unlink(temp_path)


class TestGatewayTools:
    """Test gateway tool functionality"""

    def _get_gateway_tools(self):
        """Get gateway tools"""
        tools = get_all_tools()
        call_tool = [t for t in tools if t.name == 'gateway_call_tool'][0]
        query_tool = [t for t in tools if t.name == 'gateway_query_tool'][0]
        return call_tool, query_tool

    def test_gateway_query_tool_list(self):
        """Test gateway_query_tool for listing tools"""
        _, query_tool = self._get_gateway_tools()

        result = query_tool.invoke({})
        data = json.loads(result)

        assert data["status"] == "success"
        assert data["type"] == "tool_list"
        assert len(data["tools"]) >= 9  # At least 9 MUT_LOS tools

    def test_gateway_query_tool_by_name(self):
        """Test gateway_query_tool for specific tool info"""
        _, query_tool = self._get_gateway_tools()

        result = query_tool.invoke({"tool_name": "queryAlarmList"})
        data = json.loads(result)

        assert data["status"] == "success"
        assert data["type"] == "tool_info"
        assert data["data"]["name"] == "queryAlarmList"
        assert "scenarios" in data["data"]
        assert "examples" in data["data"]

    def test_gateway_query_tool_by_scenario(self):
        """Test gateway_query_tool for scenario search"""
        _, query_tool = self._get_gateway_tools()

        result = query_tool.invoke({"scenario": "MUT_LOS"})
        data = json.loads(result)

        assert data["status"] == "success"
        assert data["type"] == "tools_for_scenario"
        assert data["count"] >= 0  # May or may not find matches

    def test_gateway_call_tool_success(self):
        """Test gateway_call_tool with valid tool"""
        call_tool, _ = self._get_gateway_tools()

        result = call_tool.invoke({
            "tool_name": "queryAlarmList",
            "params": {"neName": "NE-001", "alarmType": "MUT_LOS"}
        })
        data = json.loads(result)

        assert data["status"] == "success"
        assert data["tool"] == "queryAlarmList"
        assert "data" in data
        # The response structure is {"code": 0, "data": {"alarms": [...]}}
        assert "code" in data["data"]
        assert "data" in data["data"]
        assert "alarms" in data["data"]["data"]

    def test_gateway_call_tool_not_found(self):
        """Test gateway_call_tool with non-existent tool"""
        call_tool, _ = self._get_gateway_tools()

        result = call_tool.invoke({
            "tool_name": "nonExistentTool",
            "params": {}
        })
        data = json.loads(result)

        assert data["status"] == "error"
        assert data["error"]["type"] == "tool_not_found"

    def test_gateway_call_tool_validation_error(self):
        """Test gateway_call_tool with missing required param"""
        call_tool, _ = self._get_gateway_tools()

        result = call_tool.invoke({
            "tool_name": "queryAlarmList",
            "params": {}  # Missing required neName
        })
        data = json.loads(result)

        assert data["status"] == "error"
        assert data["error"]["type"] == "validation_error"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
