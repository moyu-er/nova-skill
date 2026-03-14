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


class TestToolCallAccumulator:
    """测试 ToolCallAccumulator 工具调用累积器"""

    def test_accumulator_with_dict_args(self):
        """测试使用字典类型的 args（完整值）"""
        from src.core.types import ToolCallAccumulator

        acc = ToolCallAccumulator()

        # 添加 tool_call，args 是字典
        acc.add_tool_call({
            'id': 'call_123',
            'name': 'search_web',
            'args': {'query': 'python tutorial'}
        })

        # 验证累积结果
        assert 'call_123' in acc
        event = acc.pop_tool_call('call_123')
        assert event is not None
        assert event.name == 'search_web'
        assert event.args == {'query': 'python tutorial'}

    def test_accumulator_with_streaming_dict_args(self):
        """测试流式传输中的 dict 类型 args（字段值分片）"""
        from src.core.types import ToolCallAccumulator

        acc = ToolCallAccumulator()

        # 模拟流式传输：dict 的字段值是分片传输的
        acc.add_tool_call({
            'id': 'call_stream',
            'name': 'read_skill_detail',
            'args': {'skill_name': 'mut'}
        })

        # 继续传输剩余部分
        acc.add_tool_call({
            'id': 'call_stream',
            'name': 'read_skill_detail',
            'args': {'skill_name': '_los'}
        })

        # 验证累积结果：字段值应该拼接起来
        event = acc.pop_tool_call('call_stream')
        assert event is not None
        assert event.name == 'read_skill_detail'
        assert event.args == {'skill_name': 'mut_los'}

    def test_accumulator_with_streaming_multiple_fields(self):
        """测试流式传输中多个字段的分片累积"""
        from src.core.types import ToolCallAccumulator

        acc = ToolCallAccumulator()

        # 第一个 chunk：部分字段值
        acc.add_tool_call({
            'id': 'call_multi',
            'name': 'search_web',
            'args': {'query': '帮我查询'}
        })

        # 第二个 chunk：继续累积
        acc.add_tool_call({
            'id': 'call_multi',
            'name': 'search_web',
            'args': {'query': '网元TEST-789'}
        })

        # 第三个 chunk：完成
        acc.add_tool_call({
            'id': 'call_multi',
            'name': 'search_web',
            'args': {'query': '的光功率告警'}
        })

        event = acc.pop_tool_call('call_multi')
        assert event is not None
        assert event.args == {'query': '帮我查询网元TEST-789的光功率告警'}

    def test_accumulator_with_json_string_args(self):
        """测试使用 JSON 字符串类型的 args（流式传输场景）"""
        from src.core.types import ToolCallAccumulator

        acc = ToolCallAccumulator()

        # 模拟流式传输：args 是部分 JSON 字符串
        acc.add_tool_call({
            'id': 'call_456',
            'name': 'search_web',
            'args': '{"query": "'
        })

        # 此时参数还未完整，不应该能弹出有效事件（但内部有数据）
        assert 'call_456' in acc

        # 继续添加剩余的 JSON
        acc.add_tool_call({
            'id': 'call_456',
            'name': 'search_web',
            'args': '4399 games"}'
        })

        # 现在 JSON 完整了，应该能解析出参数
        event = acc.pop_tool_call('call_456')
        assert event is not None
        assert event.name == 'search_web'
        assert event.args == {'query': '4399 games'}

    def test_accumulator_with_complete_json_string(self):
        """测试使用完整 JSON 字符串的 args"""
        from src.core.types import ToolCallAccumulator

        acc = ToolCallAccumulator()

        # 完整的 JSON 字符串
        acc.add_tool_call({
            'id': 'call_789',
            'name': 'fetch_url',
            'args': '{"url": "https://example.com"}'
        })

        event = acc.pop_tool_call('call_789')
        assert event is not None
        assert event.name == 'fetch_url'
        assert event.args == {'url': 'https://example.com'}

    def test_accumulator_empty_args(self):
        """测试空 args 的情况"""
        from src.core.types import ToolCallAccumulator

        acc = ToolCallAccumulator()

        # 空的 args
        acc.add_tool_call({
            'id': 'call_empty',
            'name': 'some_tool',
            'args': {}
        })

        event = acc.pop_tool_call('call_empty')
        assert event is not None
        assert event.name == 'some_tool'
        assert event.args == {}

    def test_accumulator_mixed_types_in_dict(self):
        """测试 dict 中包含字符串和非字符串值的混合"""
        from src.core.types import ToolCallAccumulator

        acc = ToolCallAccumulator()

        # 添加包含不同类型值的 dict
        acc.add_tool_call({
            'id': 'call_mixed',
            'name': 'complex_tool',
            'args': {'name': 'test', 'count': 5, 'enabled': True}
        })

        event = acc.pop_tool_call('call_mixed')
        assert event is not None
        assert event.args['name'] == 'test'
        assert event.args['count'] == 5
        assert event.args['enabled'] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
