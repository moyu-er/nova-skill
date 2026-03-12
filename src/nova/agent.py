"""
Agent 模块 - 基于 LangGraph
"""
from typing import List, Optional, AsyncGenerator, Dict, Any
from dataclasses import dataclass

from langchain_core.language_models import BaseLanguageModel
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from nova.skill import Skill, SkillRegistry


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str = "nova"
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    skills: List[str] = None  # skill 名称列表，None 表示加载所有


class Agent:
    """
    Nova Agent - 基于 LangGraph
    
    特性:
    - 从 Markdown 文件加载 Skills
    - Skills 的 system_prompt 自动合并到 Agent
    - Tools 自动绑定
    - 支持跨平台
    """
    
    def __init__(
        self,
        config: AgentConfig,
        llm: BaseLanguageModel,
        skill_registry: SkillRegistry
    ):
        self.config = config
        self.llm = llm
        self.skill_registry = skill_registry
        self._skills: List[Skill] = []
        self._system_prompt: str = ""
        self._graph = None
        
        self._load_skills()
        self._build_system_prompt()
        self._build_graph()
    
    def _load_skills(self) -> None:
        """加载配置的 skills"""
        all_skills = self.skill_registry.list_all()
        
        if self.config.skills is None:
            # 加载所有 skills
            self._skills = all_skills
            print(f"[Agent:{self.config.name}] Loaded all {len(all_skills)} skills")
        else:
            # 加载指定的 skills
            for skill_name in self.config.skills:
                skill = self.skill_registry.get(skill_name)
                if skill:
                    self._skills.append(skill)
                    print(f"[Agent:{self.config.name}] Loaded skill: {skill_name}")
                else:
                    print(f"[Agent:{self.config.name}] Skill not found: {skill_name}")
    
    def _build_system_prompt(self) -> None:
        """构建系统提示词 - 合并所有 skill 的 system_prompt"""
        parts = []
        
        # 基础提示词
        parts.append(f"你是 {self.config.name}，一个AI助手。\n")
        parts.append("你具备以下专业能力：\n")
        
        # 合并每个 skill 的 system_prompt
        for i, skill in enumerate(self._skills, 1):
            parts.append(f"\n{'='*50}")
            parts.append(f"## 能力 {i}: {skill.name}")
            parts.append(f"{'='*50}")
            parts.append(skill.system_prompt)
        
        # 添加能力标签索引
        all_caps = set()
        for skill in self._skills:
            all_caps.update(skill.capabilities)
        
        if all_caps:
            parts.append(f"\n{'='*50}")
            parts.append("## 你的能力标签")
            parts.append(f"{'='*50}")
            for cap in sorted(all_caps):
                parts.append(f"- {cap}")
        
        self._system_prompt = "\n\n".join(parts)
        
        # 打印统计
        print(f"[Agent:{self.config.name}] System prompt: {len(self._system_prompt)} chars")
        print(f"[Agent:{self.config.name}] Skills: {len(self._skills)}")
        print(f"[Agent:{self.config.name}] Capabilities: {len(all_caps)}")
    
    def _build_tools(self) -> List[StructuredTool]:
        """构建 LangChain 工具"""
        tools = []
        
        for skill in self._skills:
            for tool in skill.tools:
                if tool.func:
                    lc_tool = StructuredTool.from_function(
                        func=tool.func,
                        name=tool.name,
                        description=tool.description,
                    )
                    tools.append(lc_tool)
        
        return tools
    
    def _build_graph(self) -> None:
        """构建 LangGraph 执行图"""
        from typing import TypedDict, Annotated
        from langgraph.graph.message import add_messages
        
        class State(TypedDict):
            messages: Annotated[list, add_messages]
        
        workflow = StateGraph(State)
        tools = self._build_tools()
        
        if tools:
            # 有工具时使用 ReAct 模式
            from langgraph.prebuilt import ToolNode
            
            tool_node = ToolNode(tools)
            
            def agent_node(state: State):
                messages = [
                    SystemMessage(content=self._system_prompt)
                ] + state["messages"]
                
                response = self.llm.bind_tools(tools).invoke(messages)
                return {"messages": [response]}
            
            def should_continue(state: State):
                last_message = state["messages"][-1]
                if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
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
        else:
            # 无工具时直接对话
            def chat_node(state: State):
                messages = [
                    SystemMessage(content=self._system_prompt)
                ] + state["messages"]
                
                response = self.llm.invoke(messages)
                return {"messages": [response]}
            
            workflow.add_node("chat", chat_node)
            workflow.set_entry_point("chat")
            workflow.add_edge("chat", END)
        
        self._graph = workflow.compile(checkpointer=MemorySaver())
    
    async def astream(self, message: str, thread_id: str = None) -> AsyncGenerator[str, None]:
        """流式执行"""
        if not self._graph:
            raise RuntimeError("Agent graph not built")
        
        config = {"configurable": {"thread_id": thread_id or "default"}}
        
        async for event in self._graph.astream(
            {"messages": [HumanMessage(content=message)]},
            config
        ):
            if "messages" in event:
                msg = event["messages"][-1]
                if isinstance(msg, AIMessage) and msg.content:
                    yield msg.content
    
    async def arun(self, message: str, thread_id: str = None) -> str:
        """非流式执行"""
        result = []
        async for chunk in self.astream(message, thread_id):
            result.append(chunk)
        return "".join(result)
    
    def get_system_prompt(self) -> str:
        """获取完整的系统提示词（用于调试）"""
        return self._system_prompt
