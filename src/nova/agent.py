"""
Agent module - Supports OpenAI / Anthropic / other models

Uses LangChain universal interface, auto-detects model type
"""
import logging
import os
from typing import List, Optional, AsyncGenerator, Dict, Any, Union
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

from nova.skill import SkillRegistry
from nova.tools import get_all_tools


@dataclass
class AgentConfig:
    """Agent configuration"""
    name: str = "nova"
    model: str = "gpt-4o-mini"  # or "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    skills: List[str] = None
    # Model type: "openai" | "anthropic" | "auto"
    # auto: auto-detect based on model name
    # openai: force use OpenAI format (default when no config or config error)
    # anthropic: force use Anthropic format
    model_type: str = "auto"
    
    def __post_init__(self):
        if self.skills is None:
            self.skills = []
        # Normalize model_type
        self.model_type = self.model_type.lower().strip()
    
    @property
    def is_anthropic(self) -> bool:
        """Check if it's an Anthropic model"""
        if self.model_type == "anthropic":
            return True
        if self.model_type == "openai":
            return False
        # auto mode: detect from model name
        return "claude" in self.model.lower()
    
    @property
    def is_openai(self) -> bool:
        """Check if it's an OpenAI model"""
        if self.model_type == "openai":
            return True
        if self.model_type == "anthropic":
            return False
        # auto mode: not claude means openai-compatible
        return "claude" not in self.model.lower()


class ModelFactory:
    """Model factory - automatically creates LLM for corresponding model"""
    
    @staticmethod
    def create(config: AgentConfig, api_key: str = None, base_url: str = None) -> BaseChatModel:
        """
        Create LLM instance
        
        Auto-detects model type, uses corresponding LangChain implementation
        Defaults to OpenAI format when no config or config error
        """
        if config.is_anthropic:
            from langchain_anthropic import ChatAnthropic
            
            logger.info(f"Creating Anthropic model: {config.model}")
            
            # Build kwargs for Anthropic
            kwargs = {
                "model": config.model,
                "temperature": config.temperature,
                "streaming": True,
                "max_tokens": 4096,
            }
            
            # Only add api_key if provided
            if api_key:
                kwargs["api_key"] = api_key
            
            # Only add base_url if provided (for custom endpoints)
            if base_url:
                kwargs["base_url"] = base_url
            
            return ChatAnthropic(**kwargs)
        
        else:
            # OpenAI or other compatible models (default)
            from langchain_openai import ChatOpenAI
            
            logger.info(f"Creating OpenAI-compatible model: {config.model}")
            
            # Build kwargs for OpenAI
            kwargs = {
                "model": config.model,
                "temperature": config.temperature,
                "streaming": True,
            }
            
            # Only add api_key if provided
            if api_key:
                kwargs["api_key"] = api_key
            
            # Only add base_url if provided
            if base_url:
                kwargs["base_url"] = base_url
            
            return ChatOpenAI(**kwargs)


class Agent:
    """
    Nova Agent - Based on LangGraph
    
    Supports OpenAI, Anthropic, other compatible models
    """
    
    def __init__(
        self,
        config: AgentConfig,
        skill_registry: SkillRegistry = None,
        api_key: str = None,
        base_url: str = None,
    ):
        self.config = config
        self.skill_registry = skill_registry or SkillRegistry()
        self._skills_loaded: List[Any] = []
        
        # Create LLM
        self.llm = ModelFactory.create(config, api_key, base_url)
        
        # Build system prompt
        self._load_skills()
        self._build_system_prompt()
        
        # Build graph
        self._graph = None
        self._build_graph()
    
    def _load_skills(self) -> None:
        """Load configured skills"""
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
        """Build system_prompt"""
        import platform
        
        parts = [f"You are {self.config.name}, an AI assistant."]
        
        # Add OS information
        parts.append(f"\nCurrent Operating System: {platform.system()}")
        parts.append(f"Path Separator: {'\\\\' if platform.system() == 'Windows' else '/'}")
        parts.append("Use appropriate path formats for the current OS.")
        
        # Tell model what tools are available
        parts.append("\nYou can use the following tools:")
        parts.append("- get_system_info: Get current OS and environment information")
        parts.append("- search_web: Search for information on the web")
        parts.append("- fetch_url: Fetch content from a URL")
        parts.append("- read_file: Read a local file (supports ~ for home directory)")
        parts.append("- write_file: Write to a local file (creates directories if needed)")
        parts.append("- list_directory: List directory contents with sizes and timestamps")
        parts.append("- execute_command: Execute shell commands (use with caution)")
        parts.append("- get_current_time: Get current date and time for a specific timezone")
        parts.append("- list_timezones: List available timezones")
        parts.append("- get_available_skills: Get list of available skills")
        parts.append("- read_skill_detail: Read detailed content of a specific skill")
        
        # Tell model what skills are available (only names and descriptions, not full content)
        if self._skills_loaded:
            parts.append("\nYou can use the following skills (load details on demand):")
            for skill in self._skills_loaded:
                desc = f" - {skill.description}" if skill.description else ""
                parts.append(f"- {skill.name}{desc}")
            parts.append("\nWhen you need to use a skill, call read_skill_detail to get detailed instructions.")
        
        self._system_prompt = "\n".join(parts)
        logger.info(f"System prompt: {len(self._system_prompt)} chars")
    
    def _build_graph(self) -> None:
        """Build LangGraph"""
        from typing import TypedDict, Annotated
        from langgraph.graph.message import add_messages
        
        class State(TypedDict):
            messages: Annotated[list, add_messages]
        
        workflow = StateGraph(State)
        
        # Get all tools (framework auto-collects)
        tools = get_all_tools(self.skill_registry)
        tool_node = ToolNode(tools)
        
        def agent_node(state: State):
            """Agent node"""
            from langchain_core.messages import SystemMessage
            
            messages = [SystemMessage(content=self._system_prompt)] + state["messages"]
            response = self.llm.bind_tools(tools).invoke(messages)
            return {"messages": [response]}
        
        def should_continue(state: State):
            """Determine whether to continue"""
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
        """Stream execution - only returns content"""
        if not self._graph:
            logger.error("Graph not built")
            yield "Error: Graph not initialized"
            return
        
        from langchain_core.messages import HumanMessage
        
        config = {"configurable": {"thread_id": thread_id or "default"}}
        
        async for event in self._graph.astream(
            {"messages": [HumanMessage(content=message)]},
            config,
            stream_mode="values"
        ):
            # Get the last message
            messages = event.get("messages", [])
            if messages:
                last = messages[-1]
                # Only return AI messages with content
                if hasattr(last, 'content') and last.content:
                    if last.type == 'ai':
                        yield last.content
    
    async def astream_react(self, message: str, thread_id: str = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream execution with ReAct process"""
        if not self._graph:
            logger.error("Graph not built")
            yield {"type": "error", "content": "Graph not initialized"}
            return
        
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
        
        config = {"configurable": {"thread_id": thread_id or "default"}}
        
        seen_tool_calls = set()
        
        async for event in self._graph.astream(
            {"messages": [HumanMessage(content=message)]},
            config,
            stream_mode="values"
        ):
            messages = event.get("messages", [])
            if not messages:
                continue
            
            last = messages[-1]
            
            # Tool call detected
            if hasattr(last, 'tool_calls') and last.tool_calls:
                for tc in last.tool_calls:
                    tc_id = tc.get('id', '')
                    if tc_id not in seen_tool_calls:
                        seen_tool_calls.add(tc_id)
                        yield {
                            "type": "tool_call",
                            "name": tc.get('name', ''),
                            "args": tc.get('args', {})
                        }
            
            # Tool result
            elif isinstance(last, ToolMessage):
                yield {
                    "type": "tool_result",
                    "name": last.name,
                    "content": last.content[:500] if len(last.content) > 500 else last.content
                }
            
            # AI response
            elif isinstance(last, AIMessage) and last.content:
                yield {
                    "type": "content",
                    "content": last.content
                }
    
    def get_system_prompt(self) -> str:
        """Get current system prompt"""
        return self._system_prompt
