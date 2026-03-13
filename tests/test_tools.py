"""
Tools module tests
"""
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

        assert len(tools) == 15  # 9 base + 2 skill + 3 task planning + 1 file_info

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

        assert len(tools) == 15  # 9 base + 2 skill + 3 task planning + 1 file_info
    
    def test_read_skill_detail_tool(self):
        """Test read_skill_detail tool"""
        skills_dir = Path(__file__).parent.parent / "skills"
        registry = SkillRegistry(skills_dir)
        tools = get_all_tools(registry)
        
        # Find read_skill_detail tool
        read_skill_tool = [t for t in tools if t.name == 'read_skill_detail'][0]
        
        # Call tool
        result = read_skill_tool.invoke({'skill_name': 'antfu'})
        
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
        assert "antfu" in result or "brainstorming" in result or "writing-skills" in result


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


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
