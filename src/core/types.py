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
