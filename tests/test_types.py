"""
Types module tests - 测试枚举类和 Pydantic 模型
"""

import pytest
from src import (
    ModelType,
    EventType,
    ContentEvent,
    ToolCallEvent,
    ToolResultEvent,
    ErrorEvent,
    ReactEvent,
)


class TestModelType:
    """测试 ModelType 枚举"""

    def test_model_type_values(self):
        """测试枚举值是否正确"""
        assert ModelType.AUTO == "auto"
        assert ModelType.OPENAI == "openai"
        assert ModelType.ANTHROPIC == "anthropic"

    def test_model_type_from_string(self):
        """测试从字符串创建枚举"""
        assert ModelType("auto") == ModelType.AUTO
        assert ModelType("openai") == ModelType.OPENAI
        assert ModelType("anthropic") == ModelType.ANTHROPIC

    def test_model_type_comparison(self):
        """测试枚举比较"""
        assert ModelType.AUTO == ModelType.AUTO
        assert ModelType.OPENAI != ModelType.ANTHROPIC


class TestEventType:
    """测试 EventType 枚举"""

    def test_event_type_values(self):
        """测试枚举值是否正确"""
        assert EventType.CONTENT == "content"
        assert EventType.TOOL_CALL == "tool_call"
        assert EventType.TOOL_RESULT == "tool_result"
        assert EventType.ERROR == "error"


class TestContentEvent:
    """测试 ContentEvent 模型"""

    def test_content_event_creation(self):
        """测试创建内容事件"""
        event = ContentEvent(content="Hello world")
        assert event.type == EventType.CONTENT
        assert event.content == "Hello world"

    def test_content_event_default_type(self):
        """测试默认类型"""
        event = ContentEvent(content="test")
        assert event.type.value == "content"


class TestToolCallEvent:
    """测试 ToolCallEvent 模型"""

    def test_tool_call_event_creation(self):
        """测试创建工具调用事件"""
        event = ToolCallEvent(name="search_web", args={"query": "test"})
        assert event.type == EventType.TOOL_CALL
        assert event.name == "search_web"
        assert event.args == {"query": "test"}

    def test_tool_call_event_default_args(self):
        """测试默认参数为空字典"""
        event = ToolCallEvent(name="test_tool")
        assert event.args == {}


class TestToolResultEvent:
    """测试 ToolResultEvent 模型"""

    def test_tool_result_event_creation(self):
        """测试创建工具结果事件"""
        event = ToolResultEvent(name="search_web", content="Search results...")
        assert event.type == EventType.TOOL_RESULT
        assert event.name == "search_web"
        assert event.content == "Search results..."


class TestErrorEvent:
    """测试 ErrorEvent 模型"""

    def test_error_event_creation(self):
        """测试创建错误事件"""
        event = ErrorEvent(content="Something went wrong")
        assert event.type == EventType.ERROR
        assert event.content == "Something went wrong"


class TestReactEventUnion:
    """测试 ReactEvent 联合类型"""

    def test_react_event_can_be_any_event_type(self):
        """测试 ReactEvent 可以是任何事件类型"""
        events: list[ReactEvent] = [
            ContentEvent(content="test"),
            ToolCallEvent(name="tool", args={}),
            ToolResultEvent(name="tool", content="result"),
            ErrorEvent(content="error"),
        ]

        assert len(events) == 4
        assert isinstance(events[0], ContentEvent)
        assert isinstance(events[1], ToolCallEvent)
        assert isinstance(events[2], ToolResultEvent)
        assert isinstance(events[3], ErrorEvent)


class TestEventAccess:
    """测试事件属性访问"""

    def test_event_type_access(self):
        """测试通过 type 属性访问"""
        event = ContentEvent(content="test")
        assert event.type.value == "content"

    def test_event_content_access(self):
        """测试直接访问 content 属性"""
        event = ContentEvent(content="Hello")
        assert event.content == "Hello"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
