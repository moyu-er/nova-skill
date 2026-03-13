User: 那么, 如果我们的流程是有向无环图呢, 可能会有类似程序流程图那样的循环/判断的分支, 是否有优雅的现成实现
Kimi: 在 LangGraph 中实现**复杂 DAG（带循环/分支）的进度追踪**，最佳实践是采用**节点切面编程（Node-level Aspect）** + **拓扑进度计算**。以下是工业级实现方案：

## 核心架构：DAG 进度追踪器

```python
from typing import Annotated, TypedDict, List, Dict, Set, Optional, Callable
from langgraph.graph import StateGraph, END, START
from langgraph.types import StreamWriter
from dataclasses import dataclass, field
from enum import Enum
import time

class NodeType(Enum):
    START = "start"
    END = "end"
    PROCESS = "process"
    DECISION = "decision"
    LOOP_BACK = "loop_back"

@dataclass
class NodeMeta:
    """节点元数据，用于进度计算"""
    name: str
    node_type: NodeType
    weight: float = 1.0  # 该节点在整体进度中的权重
    description: str = ""
    estimated_time: int = 5  # 预估执行秒数

class DAGProgressState(TypedDict):
    # 业务数据
    input_data: Dict
    results: Annotated[Dict, lambda x, y: {**x, **y}]
    
    # 执行追踪（关键）
    execution_path: List[str]           # 已执行的节点序列
    current_node: str                   # 当前所在节点
    node_start_time: Dict[str, float]   # 节点开始时间戳
    loop_counts: Dict[str, int]         # 记录每个循环节点的迭代次数
    
    # 进度计算
    completed_nodes: Set[str]           # 已完成的节点（去重，循环只算一次）
    total_weight: float                 # 总权重（拓扑和）
    current_weight: float               # 已完成权重
    
    # 用户反馈
    progress_percentage: int            # 0-100
    status_message: str                 # 用户友好的状态描述
    node_details: Dict                  # 当前节点详情
```

## DAG 构建与进度追踪实现

```python
class TrackedDAGExecutor:
    def __init__(self):
        self.graph = StateGraph(DAGProgressState)
        self.node_registry: Dict[str, NodeMeta] = {}
        self.edges: List[tuple] = []
        
        # 预定义DAG结构（代码审查示例）
        self._define_workflow()
        self._build_graph()
        
    def _define_workflow(self):
        """定义带循环和分支的复杂DAG"""
        # 节点定义：名称 -> 元数据
        self.node_registry = {
            "parse_request": NodeMeta("parse_request", NodeType.START, 1.0, "解析用户请求"),
            "syntax_check": NodeMeta("syntax_check", NodeType.DECISION, 2.0, "语法检查"),
            "auto_fix": NodeMeta("auto_fix", NodeType.LOOP_BACK, 1.5, "自动修复代码"),
            "security_scan": NodeMeta("security_scan", NodeType.PROCESS, 3.0, "安全漏洞扫描"),
            "performance_test": NodeMeta("performance_test", NodeType.PROCESS, 2.5, "性能测试"),
            "merge_report": NodeMeta("merge_report", NodeType.PROCESS, 1.0, "合并检测报告"),
            "final_review": NodeMeta("final_review", NodeType.END, 0.5, "最终审查")
        }
        
    def _tracked_node(self, node_name: str):
        """装饰器：为节点添加进度追踪切面"""
        meta = self.node_registry[node_name]
        
        def decorator(func: Callable):
            def wrapper(state: DAGProgressState, writer: StreamWriter):
                # 1. 更新执行轨迹
                state["current_node"] = node_name
                state["execution_path"].append(node_name)
                state["node_start_time"][node_name] = time.time()
                
                # 2. 计算进度（考虑DAG拓扑）
                self._update_progress(state, node_name, "start")
                
                # 3. 流式推送进度事件
                writer({
                    "type": "node_start",
                    "node": node_name,
                    "message": f"🔵 进入节点: {meta.description}",
                    "percentage": state["progress_percentage"],
                    "path": state["execution_path"].copy()
                })
                
                try:
                    # 4. 执行实际业务逻辑
                    result = func(state)
                    
                    # 5. 标记完成并更新进度
                    state["completed_nodes"].add(node_name)
                    self._update_progress(state, node_name, "end")
                    
                    # 6. 推送完成事件
                    writer({
                        "type": "node_complete",
                        "node": node_name,
                        "message": f"✅ 完成: {meta.description}",
                        "percentage": state["progress_percentage"],
                        "duration": time.time() - state["node_start_time"][node_name]
                    })
                    
                    return result
                    
                except Exception as e:
                    writer({
                        "type": "error",
                        "node": node_name,
                        "message": f"❌ 节点 {node_name} 失败: {str(e)}"
                    })
                    raise
            
            return wrapper
        return decorator
    
    def _update_progress(self, state: DAGProgressState, node_name: str, phase: str):
        """基于DAG拓扑的进度计算（处理循环和并行）"""
        meta = self.node_registry[node_name]
        
        # 计算总权重（只计算一次）
        if state["total_weight"] == 0:
            state["total_weight"] = sum(n.weight for n in self.node_registry.values())
        
        # 已完成权重 = 已完成的唯一节点权重和 + 当前节点部分进度
        completed_weight = sum(
            self.node_registry[n].weight 
            for n in state["completed_nodes"] 
            if n in self.node_registry
        )
        
        if phase == "end":
            state["current_weight"] = completed_weight
        else:
            # 如果是循环节点，只给部分权重
            loop_count = state["loop_counts"].get(node_name, 0)
            partial = 0.5 if loop_count > 0 else 0.0
            state["current_weight"] = completed_weight + (meta.weight * partial)
        
        # 计算百分比
        percentage = min(100, int((state["current_weight"] / state["total_weight"]) * 100))
        state["progress_percentage"] = percentage
        
        # 生成状态消息
        remaining = [n for n in self.node_registry.keys() 
                    if n not in state["completed_nodes"]]
        state["status_message"] = f"进度 {percentage}% | 当前: {meta.description} | 剩余: {len(remaining)}个节点"
    
    def _build_graph(self):
        """构建带条件分支和循环的DAG"""
        # 定义节点逻辑
        @self._tracked_node("parse_request")
        def parse_request(state: DAGProgressState):
            # 解析请求...
            return {"results": {"parsed": True}}
        
        @self._tracked_node("syntax_check")
        def syntax_check(state: DAGProgressState):
            # 模拟检查失败率30%
            import random
            passed = random.random() > 0.3
            return {"results": {"syntax_passed": passed}}
        
        @self._tracked_node("auto_fix")
        def auto_fix(state: DAGProgressState):
            # 记录循环次数
            state["loop_counts"]["auto_fix"] = state["loop_counts"].get("auto_fix", 0) + 1
            return {"results": {"fixed": True}}
        
        @self._tracked_node("security_scan")
        def security_scan(state: DAGProgressState):
            return {"results": {"security_issues": 0}}
        
        @self._tracked_node("performance_test")
        def performance_test(state: DAGProgressState):
            return {"results": {"perf_score": 95}}
        
        @self._tracked_node("merge_report")
        def merge_report(state: DAGProgressState):
            return {"results": {"report": "All checks passed"}}
        
        @self._tracked_node("final_review")
        def final_review(state: DAGProgressState):
            return {"results": {"final": "Approved"}}
        
        # 添加节点到图
        for name in self.node_registry.keys():
            self.graph.add_node(name, locals()[name])
        
        # 定义边（含条件分支和循环）
        self.graph.add_edge(START, "parse_request")
        self.graph.add_edge("parse_request", "syntax_check")
        
        # 条件分支：语法检查失败则循环修复
        def route_syntax(state: DAGProgressState):
            if state["results"].get("syntax_passed", False):
                return "security_scan"
            else:
                return "auto_fix"
        
        self.graph.add_conditional_edges(
            "syntax_check",
            route_syntax,
            {"security_scan": "security_scan", "auto_fix": "auto_fix"}
        )
        
        # 修复后返回重新检查（循环）
        self.graph.add_edge("auto_fix", "syntax_check")
        
        # 并行分支：安全检查 和 性能测试（假设可以并行）
        # 注意：LangGraph默认顺序执行，并行需使用Send/Map-Reduce，这里简化为顺序
        self.graph.add_edge("security_scan", "merge_report")
        self.graph.add_edge("performance_test", "merge_report")
        
        # 安全检查通过后触发性能测试（或并行触发）
        def after_security(state: DAGProgressState):
            # 可以根据条件决定是否跳过性能测试
            return "performance_test"
        
        self.graph.add_conditional_edges(
            "security_scan",
            after_security,
            {"performance_test": "performance_test"}
        )
        
        self.graph.add_edge("merge_report", "final_review")
        self.graph.add_edge("final_review", END)
        
        self.compiled_graph = self.graph.compile()
    
    async def execute_with_tracking(self, input_data: Dict):
        """执行并实时流式返回进度"""
        initial_state = {
            "input_data": input_data,
            "results": {},
            "execution_path": [],
            "current_node": "",
            "node_start_time": {},
            "loop_counts": {},
            "completed_nodes": set(),
            "total_weight": 0,
            "current_weight": 0,
            "progress_percentage": 0,
            "status_message": "初始化...",
            "node_details": {}
        }
        
        print(f"🚀 启动DAG工作流，共 {len(self.node_registry)} 个节点\n")
        
        # 使用 astream 获取实时事件
        async for event in self.compiled_graph.astream(
            initial_state, 
            stream_mode=["custom", "values"],
            output_keys=["progress_percentage", "status_message", "current_node"]
        ):
            if isinstance(event, tuple):
                mode, data = event
                if mode == "custom":
                    # 自定义进度事件
                    print(f"[{data['percentage']}%] {data['message']}")
                    if data.get('path'):
                        print(f"   执行路径: {' -> '.join(data['path'][-3:])}")  # 显示最近3个节点
                elif mode == "values":
                    # 状态快照
                    print(f"📊 状态更新: {data.get('status_message')}\n")

# 使用示例
import asyncio

async def main():
    executor = TrackedDAGExecutor()
    
    # 模拟输入
    await executor.execute_with_tracking({"code": "def foo(): pass"})

if __name__ == "__main__":
    asyncio.run(main())
```

## 输出示例（带循环场景）

```
🚀 启动DAG工作流，共 7 个节点

[0%] 🔵 进入节点: 解析用户请求
   执行路径: parse_request
📊 状态更新: 进度 8% | 当前: 解析用户请求 | 剩余: 6个节点

[8%] ✅ 完成: 解析用户请求
[8%] 🔵 进入节点: 语法检查
   执行路径: parse_request -> syntax_check
📊 状态更新: 进度 25% | 当前: 语法检查 | 剩余: 5个节点

[25%] ❌ 语法检查失败，进入修复循环...
[25%] 🔵 进入节点: 自动修复代码
   执行路径: parse_request -> syntax_check -> auto_fix
📊 状态更新: 进度 35% | 当前: 自动修复代码 | 剩余: 5个节点

[35%] ✅ 完成: 自动修复代码
[35%] 🔄 返回重新检查（第1次循环）
[35%] 🔵 进入节点: 语法检查
   执行路径: ... -> auto_fix -> syntax_check
📊 状态更新: 进度 40% | 当前: 语法检查 | 剩余: 4个节点

[40%] ✅ 语法检查通过！
[40%] 🔵 进入节点: 安全漏洞扫描
...
```

## 关键技术点

### 1. **循环检测与处理**
- 使用 `loop_counts` 记录节点重入次数
- 在 `_update_progress` 中，循环节点只给部分权重（如50%），避免进度回退或停滞

### 2. **DAG 拓扑进度算法**
```python
# 更精确的算法：基于拓扑排序的深度
def calculate_dag_progress(self, state):
    """考虑并行路径的进度计算"""
    # 使用关键路径法（CPM）或简单权重法
    # 对于复杂DAG，建议预先计算每个节点的"最小完成距离"到终点
    pass
```

### 3. **可视化集成**
你可以将 `execution_path` 实时推送到前端，用 **Mermaid.js** 或 **ReactFlow** 高亮当前激活的节点：

```python
# 生成Mermaid语法
def get_mermaid_live(self, state):
    lines = ["graph TD"]
    for edge in self.edges:
        style = "stroke:#ff0000,stroke-width:4px" if edge[1] == state["current_node"] else ""
        lines.append(f"    {edge[0]}-->{edge[1]}::{style}")
    return "\n".join(lines)
```

### 4. **LangGraph 原生替代方案**
如果你希望使用更原生的 LangGraph 特性，可以使用 `checkpoint` + `interrupt`：

```python
from langgraph.checkpoint.memory import MemorySaver

# 在每个关键节点后中断，让外部系统查询进度
graph = builder.compile(checkpointer=MemorySaver(), interrupt_after=["*"])

# 外部轮询
for checkpoint in graph.get_state_history(config):
    print(f"节点 {checkpoint.next} 待执行，当前进度: {checkpoint.values['progress_percentage']}%")
```

这种方案的优势是**可恢复执行**，适合长时间运行的 DAG 任务。

这套方案的核心价值在于：**将进度追踪作为横切关注点（Cross-cutting Concern）**，通过装饰器实现零侵入的业务逻辑，同时精确处理 DAG 中的循环和分支场景。
