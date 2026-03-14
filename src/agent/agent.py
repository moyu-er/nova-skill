"""
Agent module - Supports OpenAI / Anthropic / other models

Uses LangChain universal interface, auto-detects model type
"""
import logging
import os
from typing import List, Optional, AsyncGenerator, Dict, Any, Union, TYPE_CHECKING
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessageChunk, ToolMessage

logger = logging.getLogger(__name__)
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

from ..skills import SkillRegistry
from ..tools import get_all_tools
from ..core import (
    ModelType,
    EventType,
    ContentEvent,
    ToolCallEvent,
    ToolResultEvent,
    ErrorEvent,
    ReactEvent,
    ToolCallAccumulator,
)
from ..tasks import TaskManager, TaskPlan, TaskStatus, TaskPlanner
from ..display import SimpleProgressDisplay, DisplayConfig
from ..tools import set_global_registry, set_global_task_manager


@dataclass
class AgentConfig:
    """Agent configuration"""
    name: str = "nova"
    model: str = "gpt-4o-mini"  # or "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    skills: List[str] = None
    # Model type: ModelType.AUTO | ModelType.OPENAI | ModelType.ANTHROPIC
    # AUTO: auto-detect based on model name
    # OPENAI: force use OpenAI format (default when no config or config error)
    # ANTHROPIC: force use Anthropic format
    model_type: ModelType = ModelType.AUTO
    # ReAct mode limits
    max_react_turns: int = 30  # Maximum number of agent-tool interaction turns
    max_output_tokens: int = 8192   # Maximum tokens per response

    def __post_init__(self):
        if self.skills is None:
            self.skills = []
        # Convert string to enum if needed
        if isinstance(self.model_type, str):
            self.model_type = ModelType(self.model_type.lower().strip())

    @property
    def is_anthropic(self) -> bool:
        """Check if it's an Anthropic model"""
        if self.model_type == ModelType.ANTHROPIC:
            return True
        if self.model_type == ModelType.OPENAI:
            return False
        # auto mode: detect from model name
        return "claude" in self.model.lower()

    @property
    def is_openai(self) -> bool:
        """Check if it's an OpenAI model"""
        if self.model_type == ModelType.OPENAI:
            return True
        if self.model_type == ModelType.ANTHROPIC:
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

        # Task planning
        self.task_planner: Optional[TaskPlanner] = None
        self._task_mode = False
        self._task_manager = TaskManager()

        # Set global instances for tool registration
        set_global_registry(self.skill_registry)
        set_global_task_manager(self._task_manager)

        # Progress display
        self._progress_display: Optional[SimpleProgressDisplay] = None
        self._display_config = DisplayConfig()

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

        # Task planning guidance - encourage model to plan for complex tasks
        parts.append("\n---")
        parts.append("TASK PLANNING GUIDANCE:")
        parts.append("For complex multi-step tasks, you SHOULD create a task plan first.")
        parts.append("Call 'create_task_plan' to break down the request into manageable steps.")
        parts.append("This helps track progress and ensures nothing is missed.")
        parts.append("Examples of when to plan:")
        parts.append("- Projects requiring multiple file operations")
        parts.append("- Tasks with dependencies between steps")
        parts.append("- Complex refactoring or implementation work")
        parts.append("- Multi-stage analysis or data processing")
        parts.append("After creating a plan, you can track progress with 'get_task_status' and 'update_task_status'.")
        parts.append("---")

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
            turn_count: int  # Track agent-tool interaction turns

        workflow = StateGraph(State)

        # Get base tools (excluding task planning tools - we'll handle those specially)
        base_tools = get_all_tools(self.skill_registry, None)

        # Define task planning tool schemas for LLM to use
        task_planning_tool_schemas = self._get_task_planning_tool_schemas()
        all_tool_schemas = base_tools + task_planning_tool_schemas

        # Create tool node for base tools
        base_tool_node = ToolNode(base_tools)

        def agent_node(state: State):
            """Agent node"""
            from langchain_core.messages import SystemMessage

            messages = [SystemMessage(content=self._system_prompt)] + state["messages"]

            # Check turn limit - if exceeded, don't bind tools to force final response
            current_turn = state.get("turn_count", 0)
            if current_turn >= self.config.max_react_turns:
                logger.warning(f"ReAct turn limit reached: {current_turn}, forcing final response")
                response = self.llm.invoke(messages)
            else:
                response = self.llm.bind_tools(all_tool_schemas).invoke(messages)
            return {"messages": [response]}

        def should_continue(state: State):
            """Determine whether to continue"""
            last = state["messages"][-1]
            if hasattr(last, 'tool_calls') and last.tool_calls:
                return "tools"
            return END

        async def tools_node(state: State):
            """Custom tools node - handles base tools and task planning tools"""
            from langchain_core.messages import ToolMessage

            last_message = state["messages"][-1]
            if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
                return {"messages": [], "turn_count": state.get("turn_count", 0)}

            results = []
            for tool_call in last_message.tool_calls:
                tool_name = tool_call.get('name', '')
                tool_args = tool_call.get('args', {})
                tool_id = tool_call.get('id', '')

                # Handle task planning tools specially
                if tool_name == "create_task_plan":
                    result = await self._handle_create_task_plan(tool_args)
                elif tool_name == "get_task_status":
                    result = self._handle_get_task_status()
                elif tool_name == "update_task_status":
                    result = self._handle_update_task_status(tool_args)
                else:
                    # Use base tool node for other tools
                    result = await self._execute_base_tool(tool_name, tool_args, base_tools)

                results.append(ToolMessage(content=str(result), name=tool_name, tool_call_id=tool_id))

            # Increment turn count after tool execution
            return {"messages": results, "turn_count": state.get("turn_count", 0) + 1}

        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tools_node)
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges("agent", should_continue, {
            "tools": "tools",
            END: END
        })
        workflow.add_edge("tools", "agent")

        self._graph = workflow.compile(checkpointer=MemorySaver())
        logger.info("Graph compiled")

    def _get_task_planning_tool_schemas(self):
        """Get task planning tool schemas for LLM"""
        from langchain_core.tools import StructuredTool
        from typing import Annotated

        async def create_task_plan_stub(query: Annotated[str, "The task description to plan"]) -> str:
            """
            Create a task plan for complex multi-step requests.

            Use this tool when the user has a complex request that needs to be broken down into steps.
            The plan will be saved and can be tracked.

            Args:
                query: The complex task description to plan

            Returns:
                Task plan details with task list
            """
            return "Task plan creation requested"

        def get_task_status_stub() -> str:
            """
            Get current task plan status and progress.

            Returns:
                Current task plan status with progress information
            """
            return "Task status requested"

        def update_task_status_stub(
            task_id: Annotated[int, "Task ID to update"],
            status: Annotated[str, "New status: pending, in_progress, completed, failed"],
            result: Annotated[str, "Task result or output"] = ""
        ) -> str:
            """
            Update a task's status in the current plan.

            Args:
                task_id: The task ID to update
                status: New status (pending, in_progress, completed, failed)
                result: Optional task result

            Returns:
                Update confirmation
            """
            return f"Task {task_id} status update requested"

        return [
            StructuredTool.from_function(create_task_plan_stub, name="create_task_plan"),
            StructuredTool.from_function(get_task_status_stub, name="get_task_status"),
            StructuredTool.from_function(update_task_status_stub, name="update_task_status"),
        ]

    async def _handle_create_task_plan(self, args: dict) -> str:
        """Handle create_task_plan tool call"""
        query = args.get("query", "")
        if not query:
            return "Error: No query provided"

        try:
            plan = await self.create_task_plan(query)
            tasks_summary = "\n".join([f"{i+1}. {t.subject}" for i, t in enumerate(plan.tasks)])
            return f"Task plan created with {len(plan.tasks)} tasks:\n{tasks_summary}"
        except Exception as e:
            import traceback
            error_msg = str(e)
            error_detail = traceback.format_exc()
            logger.error(f"Error creating task plan: {error_msg}\n{error_detail}")
            return f"Error creating task plan: {error_msg}\nDetail: {error_detail[:200]}..."

    def _handle_get_task_status(self) -> str:
        """Handle get_task_status tool call"""
        plan = self.get_current_task_plan()
        if not plan:
            return "No active task plan."

        lines = [f"Task Plan: {plan.query}", f"Progress: {plan.completed_tasks}/{plan.total_tasks}", ""]
        for task in plan.tasks:
            status_icon = {"pending": "○", "in_progress": "◎", "completed": "✓", "failed": "✗"}.get(task.status.value, "?")
            lines.append(f"{status_icon} {task.subject}")

        return "\n".join(lines)

    def _handle_update_task_status(self, args: dict) -> str:
        """Handle update_task_status tool call"""
        try:
            task_id = int(args.get("task_id", 0))
            status_str = args.get("status", "")
            result = args.get("result", "")

            task_status = TaskStatus(status_str)
            task = self.update_task_status(task_id, task_status, result)

            # 更新进度显示
            self._update_progress_display()

            if task:
                return f"Task {task_id} updated to {status_str}"
            return f"Task {task_id} not found"
        except (ValueError, KeyError) as e:
            return f"Error updating task: {e}"

    async def _execute_base_tool(self, tool_name: str, tool_args: dict, base_tools: list) -> str:
        """Execute a base tool"""
        for tool in base_tools:
            if tool.name == tool_name:
                try:
                    if hasattr(tool, 'ainvoke'):
                        return await tool.ainvoke(tool_args)
                    else:
                        return tool.invoke(tool_args)
                except Exception as e:
                    return f"Error executing {tool_name}: {e}"
        return f"Tool {tool_name} not found"

    async def astream(self, message: str, thread_id: str = None) -> AsyncGenerator[str, None]:
        """Stream execution - only returns content (true streaming)"""
        if not self._graph:
            logger.error("Graph not built")
            yield "Error: Graph not initialized"
            return

        config = {"configurable": {"thread_id": thread_id or "default"}}

        async for event in self._graph.astream(
            {"messages": [HumanMessage(content=message)]},
            config,
            stream_mode="messages"
        ):
            # stream_mode="messages" returns (message_chunk, metadata) tuple
            if isinstance(event, tuple) and len(event) >= 1:
                chunk = event[0]
                # Only yield AI message chunks with content
                if isinstance(chunk, AIMessageChunk) and chunk.content:
                    yield chunk.content

    async def astream_react(self, message: str, thread_id: str = None) -> AsyncGenerator[ReactEvent, None]:
        """Stream execution with ReAct process (true streaming)"""
        if not self._graph:
            logger.error("Graph not built")
            yield ErrorEvent(content="Graph not initialized")
            return

        config = {"configurable": {"thread_id": thread_id or "default"}}

        # Accumulate tool calls across chunks for proper streaming display
        tc_accumulator = ToolCallAccumulator()
        token_count = 0
        max_tokens = self.config.max_output_tokens

        async for event in self._graph.astream(
            {"messages": [HumanMessage(content=message)], "turn_count": 0},
            config,
            stream_mode="messages"
        ):
            # stream_mode="messages" returns (message_chunk, metadata) tuple
            if not isinstance(event, tuple) or len(event) < 1:
                continue

            chunk = event[0]

            # Tool call detected (in AIMessageChunk with tool_calls)
            # Accumulate args across chunks
            if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                for tc in chunk.tool_calls:
                    tc_accumulator.add_tool_call(tc)

            # Tool result - emit the accumulated tool call before the result
            elif isinstance(chunk, ToolMessage):
                tc_id = chunk.tool_call_id

                # Emit the accumulated tool call and remove from cache
                # ToolMessage indicates the tool call args are fully accumulated
                if tc_id in tc_accumulator:
                    tc_event = tc_accumulator.pop_tool_call(tc_id)
                    if tc_event:
                        yield tc_event

                yield ToolResultEvent(
                    name=chunk.name,
                    content=chunk.content[:500] if len(chunk.content) > 500 else chunk.content
                )

            # AI response chunk (streaming)
            elif isinstance(chunk, AIMessageChunk) and chunk.content:
                content = chunk.content
                # Check token limit (approximate: 1 token ~= 4 chars for English, 1 char for CJK)
                estimated_tokens = len(content) // 2  # Conservative estimate
                if token_count + estimated_tokens > max_tokens:
                    remaining = max_tokens - token_count
                    if remaining > 0:
                        content = content[:remaining * 2]
                        yield ContentEvent(content=content)
                    yield ErrorEvent(content=f"\n[Output truncated: reached max token limit ({max_tokens})]")
                    break
                token_count += estimated_tokens
                yield ContentEvent(content=content)

    async def create_task_plan(self, query: str) -> TaskPlan:
        """创建任务计划"""
        if not self.task_planner:
            self.task_planner = TaskPlanner(self.llm)
            # 使用 Agent 的 task_manager
            self.task_planner.task_manager = self._task_manager

        plan = await self.task_planner.create_plan(query)
        self._task_mode = True
        return plan

    def get_current_task_plan(self) -> Optional[TaskPlan]:
        """获取当前任务计划"""
        return self._task_manager.get_current_plan()

    def update_task_status(self, task_id: int, status: TaskStatus, result: str = None, error: str = None):
        """更新任务状态"""
        return self._task_manager.update_task_status(task_id, status, result, error)

    def get_next_task(self) -> Optional[dict]:
        """获取下一个可执行的任务"""
        task = self._task_manager.get_next_task()
        if task:
            return {
                "id": task.id,
                "subject": task.subject,
                "description": task.description,
            }
        return None

    def complete_task_plan(self):
        """完成任务计划"""
        # 打印任务汇总
        if self._progress_display:
            plan = self._task_manager.get_current_plan()
            if plan:
                self._progress_display.print_summary(plan)
            self._progress_display.reset()

        self._task_manager.complete_plan()
        self._task_mode = False
        self._progress_display = None

    def _update_progress_display(self):
        """更新进度显示"""
        if not self._task_mode:
            return

        plan = self._task_manager.get_current_plan()
        if not plan:
            return

        # 初始化进度显示器
        if self._progress_display is None:
            self._progress_display = SimpleProgressDisplay()

        # 更新显示
        self._progress_display.update(plan)

    def is_task_mode(self) -> bool:
        """检查是否处于任务模式"""
        return self._task_mode

    def get_system_prompt(self) -> str:
        """Get current system prompt"""
        return self._system_prompt
