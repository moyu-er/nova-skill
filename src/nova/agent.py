"""
Agent 模块 - 支持 OpenAI / Anthropic / 其他模型

使用 LangChain 通用接口，自动识别模型类型
"""
import logging
from typing import List, Optional, AsyncGenerator, Dict, Any, Union
from dataclasses import dataclass
from pathlib import Path

from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

from nova.skill import SkillRegistry
from nova.tools import get_all_tools


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str = "nova"
    model: str = "gpt-4o-mini"  # 或 "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    skills: List[str] = None
    
    @property
    def is_anthropic(self) -> bool:
        """判断是否为 Anthropic 模型"""
        return "claude" in self.model.lower()
    
    @property
    def is_openai(self) -> bool:
        """判断是否为 OpenAI 模型"""
        return any(x in self.model.lower() for x in ["gpt", "o1", "o3"])


class ModelFactory:
    """模型工厂 - 自动创建对应模型的 LLM"""
    
    @staticmethod
    def create(config: AgentConfig, api_key: str = None, base_url: str = None) -> BaseChatModel:
        """
        创建 LLM 实例
        
        自动识别模型类型，使用对应的 LangChain 实现
        """
        if config.is_anthropic:
            from langchain_anthropic import ChatAnthropic
            
            logger.info(f"Creating Anthropic model: {config.model}")
            return ChatAnthropic(
                model=config.model,
                temperature=config.temperature,
                anthropic_api_key=api_key,
                anthropic_api_url=base_url,
                streaming=True,
                max_tokens=4096,
            )
        
        elif config.is_openai:
            from langchain_openai import ChatOpenAI
            
            logger.info(f"Creating OpenAI model: {config.model}")
            return ChatOpenAI(
                model=config.model,
                temperature=config.temperature,
                api_key=api_key,
                base_url=base_url,
                streaming=True,
            )
        
        else:
            # 其他模型（通过 OpenAI 兼容接口）
            from langchain_openai import ChatOpenAI
            
            logger.info(f"Creating OpenAI-compatible model: {config.model}")
            return ChatOpenAI(
                model=config.model,
                temperature=config.temperature,
                api_key=api_key,
                base_url=base_url,
                streaming=True,
            )


class Agent:
    """
    Nova Agent - 基于 LangGraph
    
    支持 OpenAI、Anthropic、其他兼容模型
    """
    
    def __init__(
        self,
        config: AgentConfig,
        llm: BaseChatModel = None,
        skill_registry: SkillRegistry = None,
        api_key: str = None,
        base_url: str = None
    ):
        self.config = config
        self.skill_registry = skill_registry or SkillRegistry()
        self._skills_loaded = []
        self._system_prompt: str = ""
        self._graph = None
        
        # 创建或接收 LLM
        if llm is None:
            self.llm = ModelFactory.create(config, api_key, base_url)
        else:
            self.llm = llm
        
        self._load_skills()
        self._build_system_prompt()
        self._build_graph()
    
    def _load_skills(self) -> None:
        """加载配置的 skills"""
        if not self.config.skills:
            return
        
        for skill_name in self.config.skills:
            skill = self.skill_registry.get(skill_name)
            if skill:
                self._skills_loaded.append(skill)
                logger.info(f"Loaded skill: {skill_name}")
            else:
                logger.warning(f"Skill not found: {skill_name}")
    
    def _build_system_prompt(self) -> None:
        """构建 system_prompt"""
        parts = [f"你是 {self.config.name}，一个AI助手。"]
        
        # 告诉模型可以使用工具
        parts.append("\n你可以使用以下工具：")
        parts.append("- search_web: 搜索网络信息")
        parts.append("- fetch_url: 获取网页内容")
        parts.append("- read_file: 读取本地文件")
        parts.append("- write_file: 写入本地文件")
        parts.append("- list_directory: 列出目录内容")
        parts.append("- get_available_skills: 获取可用 skills")
        parts.append("- read_skill_detail: 读取 skill 详细内容")
        
        # 合并 skill system_prompts
        for skill in self._skills_loaded:
            if skill.system_prompt:
                parts.append(f"\n=== {skill.name} ===\n{skill.system_prompt}")
        
        self._system_prompt = "\n".join(parts)
        logger.info(f"System prompt: {len(self._system_prompt)} chars")
    
    def _build_graph(self) -> None:
        """构建 LangGraph"""
        from typing import TypedDict, Annotated
        from langgraph.graph.message import add_messages
        
        class State(TypedDict):
            messages: Annotated[list, add_messages]
        
        workflow = StateGraph(State)
        
        # 获取所有工具（框架自动收集）
        tools = get_all_tools(self.skill_registry)
        tool_node = ToolNode(tools)
        
        def agent_node(state: State):
            """Agent 节点"""
            from langchain_core.messages import SystemMessage
            
            messages = [SystemMessage(content=self._system_prompt)] + state["messages"]
            response = self.llm.bind_tools(tools).invoke(messages)
            return {"messages": [response]}
        
        def should_continue(state: State):
            """判断是否继续"""
            last = state["messages"][-1]
            if hasattr(last, 'tool_calls') and last.tool_calls:
                return "tools"
            return END
        
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges("agent", should_continue, {
            "tools": "tools",
            END: END
        })
        workflow.add_edge("tools", "agent")
        
        self._graph = workflow.compile(checkpointer=MemorySaver())
        logger.info("Graph compiled")
    
    async def astream(self, message: str, thread_id: str = None) -> AsyncGenerator[str, None]:
        """流式执行"""
        if not self._graph:
            logger.error("Graph not built")
            return
        
        config = {"configurable": {"thread_id": thread_id or "default"}}
        
        logger.info(f"Streaming for thread: {thread_id}")
        
        from langchain_core.messages import HumanMessage
        
        async for event in self._graph.astream(
            {"messages": [HumanMessage(content=message)]},
            config
        ):
            if "messages" in event:
                msg = event["messages"][-1]
                if isinstance(msg, type(event["messages"][0])) and hasattr(msg, 'content'):
                    if msg.content:
                        yield msg.content
    
    async def arun(self, message: str, thread_id: str = None) -> str:
        """非流式执行"""
        result = []
        async for chunk in self.astream(message, thread_id):
            result.append(chunk)
        return "".join(result)
