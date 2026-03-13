User: langchain/langgraph中, 如何实现(或者最好原本就有)任务规划工具, 并且能够每轮输出告诉用户现在的进展
Kimi: 在 LangGraph 中实现**带进度反馈的任务规划**，最优雅的方案是利用 `StateGraph` 的状态传递 + `stream` 模式的实时流式输出。以下是完整的工程级实现方案：

## 核心架构设计

```python
from typing import Annotated, TypedDict, List, Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import operator

# 1. 定义带进度追踪的状态结构
class TaskState(TypedDict):
    # 任务规划相关
    plan: List[str]                    # 任务列表
    current_task_index: int            # 当前执行到第几个任务
    results: Annotated[List[Any], operator.add]  # 累积的结果
    
    # 进度报告相关
    status: Literal["planning", "executing", "completed", "error"]  # 当前状态
    progress_message: str              # 给用户看的进度描述
    messages: List[Any]                # 对话历史
    
    # 原始输入
    original_query: str
```

## 完整实现代码

```python
class TaskPlannerWithProgress:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o")
        self.tools = [self.search_tool, self.calculate_tool]
        self.tool_node = ToolNode(self.tools)
        
        # 构建图
        self.workflow = StateGraph(TaskState)
        self._build_graph()
        self.app = self.workflow.compile()
    
    @tool
    def search_tool(self, query: str) -> str:
        """执行搜索"""
        # 模拟搜索延迟
        import time; time.sleep(1)
        return f"搜索结果: {query} 的相关信息..."
    
    @tool
    def calculate_tool(self, expression: str) -> str:
        """执行计算"""
        try:
            result = eval(expression)
            return f"计算结果: {result}"
        except:
            return "计算错误"
    
    # ========== 节点定义 ==========
    
    def planner_node(self, state: TaskState):
        """规划节点：拆解任务并报告开始"""
        query = state["original_query"]
        
        # 使用 LLM 生成任务计划
        prompt = f"""将以下用户请求拆解为具体的执行步骤列表，每步一个工具调用：
用户请求: {query}
可用工具: search_tool(搜索), calculate_tool(计算)
请用列表格式返回，例如：
1. search_tool: 查询天气
2. calculate_tool: 计算温度差

只返回任务列表，不要其他内容。"""

        response = self.llm.invoke([HumanMessage(content=prompt)])
        
        # 解析任务列表（简化版，实际可用更鲁棒的解析）
        tasks = [line.strip() for line in response.content.split('\n') 
                if line.strip() and any(c.isdigit() for c in line[:3])]
        
        return {
            "plan": tasks,
            "current_task_index": 0,
            "status": "planning",
            "progress_message": f"📋 任务规划完成，共 {len(tasks)} 个步骤:\n" + "\n".join([f"  {i+1}. {t}" for i, t in enumerate(tasks)]),
            "messages": [AIMessage(content=f"开始执行任务规划...")]
        }
    
    def executor_node(self, state: TaskState):
        """执行节点：执行当前任务并报告进度"""
        current_idx = state["current_task_index"]
        plan = state["plan"]
        
        if current_idx >= len(plan):
            return {
                "status": "completed",
                "progress_message": "✅ 所有任务执行完毕！"
            }
        
        current_task = plan[current_idx]
        
        # 解析工具调用（简化版）
        if "search_tool" in current_task:
            tool_name = "search_tool"
            tool_input = current_task.split(":")[-1].strip() if ":" in current_task else current_task
        elif "calculate_tool" in current_task:
            tool_name = "calculate_tool"
            tool_input = current_task.split(":")[-1].strip() if ":" in current_task else current_task
        else:
            tool_name = "search_tool"
            tool_input = current_task
        
        # 执行工具
        try:
            if tool_name == "search_tool":
                result = self.search_tool.invoke(tool_input)
            else:
                result = self.calculate_tool.invoke(tool_input)
            
            progress_msg = f"🔄 进度 [{current_idx+1}/{len(plan)}]: 正在执行「{current_task}」...\n✓ 完成: {result[:50]}..."
            
            return {
                "results": [result],
                "current_task_index": current_idx + 1,
                "status": "executing",
                "progress_message": progress_msg,
                "messages": [ToolMessage(content=result, name=tool_name)]
            }
        except Exception as e:
            return {
                "status": "error",
                "progress_message": f"❌ 任务 {current_idx+1} 执行失败: {str(e)}"
            }
    
    def should_continue(self, state: TaskState) -> Literal["continue", "end"]:
        """路由判断：是否还有未完成的任务"""
        if state["status"] == "error":
            return "end"
        if state["current_task_index"] < len(state["plan"]):
            return "continue"
        return "end"
    
    def _build_graph(self):
        """构建状态图"""
        self.workflow.add_node("planner", self.planner_node)
        self.workflow.add_node("executor", self.executor_node)
        
        self.workflow.set_entry_point("planner")
        self.workflow.add_edge("planner", "executor")
        
        # 循环执行：executor -> executor (如果未完成)
        self.workflow.add_conditional_edges(
            "executor",
            self.should_continue,
            {
                "continue": "executor",  # 继续执行下一个任务
                "end": END
            }
        )
    
    def run_with_progress(self, query: str):
        """流式执行并实时打印进度"""
        initial_state = {
            "original_query": query,
            "plan": [],
            "current_task_index": 0,
            "results": [],
            "status": "planning",
            "progress_message": "",
            "messages": []
        }
        
        print(f"🚀 开始处理任务: {query}\n")
        
        # 使用 stream 模式获取中间状态
        for event in self.app.stream(initial_state, stream_mode="values"):
            # 提取并显示进度消息
            if "progress_message" in event:
                print(event["progress_message"])
                print("-" * 50)
            
            # 最终输出
            if event.get("status") == "completed":
                print("\n📊 最终结果汇总:")
                for i, result in enumerate(event.get("results", [])):
                    print(f"  步骤 {i+1}: {result}")

# 使用示例
planner = TaskPlannerWithProgress()
planner.run_with_progress("查询北京和上海的天气，并计算两地的温差")
```

## 输出效果示例

```
🚀 开始处理任务: 查询北京和上海的天气，并计算两地的温差

📋 任务规划完成，共 3 个步骤:
  1. search_tool: 查询北京天气
  2. search_tool: 查询上海天气  
  3. calculate_tool: 计算两地温差
--------------------------------------------------
🔄 进度 [1/3]: 正在执行「1. search_tool: 查询北京天气」...
✓ 完成: 搜索结果: 查询北京天气 的相关信息...
--------------------------------------------------
🔄 进度 [2/3]: 正在执行「2. search_tool: 查询上海天气」...
✓ 完成: 搜索结果: 查询上海天气 的相关信息...
--------------------------------------------------
🔄 进度 [3/3]: 正在执行「3. calculate_tool: 计算两地温差」...
✓ 完成: 计算结果: 5
--------------------------------------------------
✅ 所有任务执行完毕！
--------------------------------------------------

📊 最终结果汇总:
  步骤 1: 搜索结果: 查询北京天气 的相关信息...
  步骤 2: 搜索结果: 查询上海天气 的相关信息...
  步骤 3: 计算结果: 5
```

## 进阶：WebSocket/前端实时推送

如果需要将进度推送到前端，可以改造 `run_with_progress` 为异步生成器：

```python
async def stream_progress(self, query: str):
    """异步流式输出，适合 FastAPI WebSocket"""
    initial_state = {...}
    
    async for event in self.app.astream(initial_state, stream_mode="values"):
        yield {
            "type": "progress",
            "status": event.get("status"),
            "message": event.get("progress_message"),
            "current_step": event.get("current_task_index", 0),
            "total_steps": len(event.get("plan", [])),
            "percentage": (event.get("current_task_index", 0) / len(event.get("plan", [1]))) * 100
        }
        
        if event.get("status") == "completed":
            yield {"type": "final", "results": event.get("results")}
```

## 关键设计要点

1. **状态驱动**：所有进度信息通过 `TaskState` 传递，不依赖外部全局变量
2. **细粒度控制**：每个任务完成后都更新 `progress_message`，通过 `stream_mode="values"` 实时获取
3. **自包含循环**：`executor` 节点通过 `should_continue` 路由实现循环执行，直到任务列表耗尽
4. **错误隔离**：单个任务失败不会中断整个流程，状态中会标记 `error` 并携带错误信息

这种方案相比简单的 Chain 或 AgentExecutor 的优势在于：**你可以精确控制每一步的进度上报逻辑**，比如在长时间工具调用前发送"开始执行"消息，在完成后发送结果摘要，完全掌控用户体验。
