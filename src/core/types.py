"""
类型定义模块 - 枚举类和 Pydantic 模型

提供类型安全的枚举和结构化数据模型
"""
from enum import Enum, auto
from typing import Any, Optional
from pydantic import BaseModel, Field


class ModelType(str, Enum):
    """模型类型枚举"""
    AUTO = "auto"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class EventType(str, Enum):
    """事件类型枚举 - 用于 astream_react"""
    CONTENT = "content"      # AI 内容输出
    TOOL_CALL = "tool_call"  # 工具调用
    TOOL_RESULT = "tool_result"  # 工具结果
    ERROR = "error"          # 错误


class StreamEvent(BaseModel):
    """流事件基础模型"""
    type: EventType


class ContentEvent(StreamEvent):
    """内容事件 - AI 生成的文本内容"""
    type: EventType = EventType.CONTENT
    content: str = Field(description="文本内容片段")


class ToolCallEvent(StreamEvent):
    """工具调用事件"""
    type: EventType = EventType.TOOL_CALL
    name: str = Field(description="工具名称")
    args: dict = Field(default_factory=dict, description="工具参数")


class ToolCallAccumulator:
    """
    累积流式 tool_calls 的参数，缓存并等待拼接完成后输出

    LangChain 的流式输出中，tool_calls 的 args 可能分多个 chunk 传输。
    此类负责：
    1. 累积分段的参数（不立即输出）
    2. 在 ToolMessage 到达时（表示参数拼接完成），输出完整的 tool_call
    3. 输出后从缓存中移除

    使用方式:
        accumulator = ToolCallAccumulator()

        # 在收到 AIMessageChunk 时累积参数（不输出）
        for tc in chunk.tool_calls:
            accumulator.add_tool_call(tc)

        # 在收到 ToolMessage 时，输出完整的 tool_call 并清理
        if chunk.tool_call_id in accumulator:
            event = accumulator.pop_tool_call(chunk.tool_call_id)
            if event:
                yield event
    """

    def __init__(self):
        # {tool_call_id: {'name': str, 'args': dict, '_field_buffers': dict}}
        self._tool_calls: dict[str, dict] = {}

    def add_tool_call(self, tool_call: dict) -> None:
        """
        添加或更新 tool_call（仅累积，不输出）

        在流式传输中，args 可能是分片传输的：
        - dict 类型：字段值是部分字符串，需要拼接
        - str 类型：JSON 字符串片段，需要累积后解析

        Args:
            tool_call: LangChain tool_call dict with 'id', 'name', 'args'
        """
        import json

        tc_id = tool_call.get('id', '')
        if not tc_id:
            return

        tc_name = tool_call.get('name', '')
        tc_args = tool_call.get('args', {})

        # Initialize if not exists
        if tc_id not in self._tool_calls:
            self._tool_calls[tc_id] = {
                'name': tc_name,
                'args': {},
                '_field_buffers': {},  # 用于累积每个字段的部分值 {field_name: accumulated_string}
                '_json_buffer': '',    # 用于累积 JSON 字符串
            }

        # Update name if provided (should be consistent, but just in case)
        if tc_name:
            self._tool_calls[tc_id]['name'] = tc_name

        # Handle args
        if not tc_args:
            return

        if isinstance(tc_args, dict):
            # Args 是 dict，但字段值可能是分片传输的字符串
            for key, value in tc_args.items():
                if isinstance(value, str):
                    # 字符串值：累积到缓冲区
                    if key not in self._tool_calls[tc_id]['_field_buffers']:
                        self._tool_calls[tc_id]['_field_buffers'][key] = ''
                    self._tool_calls[tc_id]['_field_buffers'][key] += value
                    # 更新到 args
                    self._tool_calls[tc_id]['args'][key] = self._tool_calls[tc_id]['_field_buffers'][key]
                else:
                    # 非字符串值（如数字、布尔值）：直接设置
                    self._tool_calls[tc_id]['args'][key] = value
                    # 清除该字段的缓冲区（如果有）
                    if key in self._tool_calls[tc_id]['_field_buffers']:
                        del self._tool_calls[tc_id]['_field_buffers'][key]

        elif isinstance(tc_args, str):
            # Args 是 JSON 字符串片段，累积后尝试解析
            self._tool_calls[tc_id]['_json_buffer'] += tc_args
            try:
                parsed_args = json.loads(self._tool_calls[tc_id]['_json_buffer'])
                if isinstance(parsed_args, dict):
                    # 解析成功，合并到 args（同样使用字符串拼接逻辑）
                    for key, value in parsed_args.items():
                        if isinstance(value, str):
                            if key not in self._tool_calls[tc_id]['_field_buffers']:
                                self._tool_calls[tc_id]['_field_buffers'][key] = ''
                            self._tool_calls[tc_id]['_field_buffers'][key] += value
                            self._tool_calls[tc_id]['args'][key] = self._tool_calls[tc_id]['_field_buffers'][key]
                        else:
                            self._tool_calls[tc_id]['args'][key] = value
                    # 清除 JSON 缓冲区
                    self._tool_calls[tc_id]['_json_buffer'] = ''
            except json.JSONDecodeError:
                # JSON 不完整，等待更多数据
                pass

    def pop_tool_call(self, tool_call_id: str) -> ToolCallEvent | None:
        """
        获取并移除累积的 tool_call 事件

        在 ToolMessage 到达时调用，表示参数拼接已完成。
        返回完整的 tool_call 事件并从缓存中移除。

        Args:
            tool_call_id: tool_call ID

        Returns:
            ToolCallEvent with accumulated args, or None if not found
        """
        if tool_call_id not in self._tool_calls:
            return None

        tc = self._tool_calls.pop(tool_call_id)
        return ToolCallEvent(name=tc['name'], args=tc['args'])

    def __contains__(self, tool_call_id: str) -> bool:
        """支持 'in' 操作符"""
        return tool_call_id in self._tool_calls

    def clear(self) -> None:
        """清空所有累积的 tool_calls"""
        self._tool_calls.clear()


class ToolResultEvent(StreamEvent):
    """工具结果事件"""
    type: EventType = EventType.TOOL_RESULT
    name: str = Field(description="工具名称")
    content: str = Field(description="工具执行结果")


class ErrorEvent(StreamEvent):
    """错误事件"""
    type: EventType = EventType.ERROR
    content: str = Field(description="错误信息")


# 联合类型
ReactEvent = ContentEvent | ToolCallEvent | ToolResultEvent | ErrorEvent
