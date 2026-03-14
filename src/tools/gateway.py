"""
Tool Gateway - Flexible tool registration and invocation gateway

Features:
- @gateway_tool decorator for registering functions
- Pydantic-based parameter validation
- Tool metadata query (usage, scenarios, examples)
- Exception handling with structured error responses
- Coexists with regular @tool decorated functions

Usage:
    from src.tools.gateway import gateway_tool, ToolGateway

    # Register a tool with the gateway
    @gateway_tool(
        name="queryAlarmList",
        description="Query alarm list from network element",
        scenarios=["When user asks about MUT_LOS alarms", "When checking alarm status"],
        examples=[
            {"params": {"neName": "NE-001", "alarmType": "MUT_LOS"}, "description": "Query MUT_LOS alarms"}
        ]
    )
    def query_alarm_list(neName: str, alarmType: str = "MUT_LOS", **kwargs) -> dict:
        return {"alarms": [...]}

    # Model calls via gateway
    result = await gateway.call_tool("queryAlarmList", {"neName": "NE-001"})

    # Query tool metadata
    metadata = gateway.get_tool_info("queryAlarmList")
"""

import json
import inspect
import functools
from typing import (
    Any, Callable, Dict, List, Optional, Type, Union, get_type_hints, get_origin, get_args
)
from dataclasses import dataclass, field, asdict
from enum import Enum

from pydantic import BaseModel, ValidationError, create_model, Field
from langchain_core.tools import tool


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Metadata Classes
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ToolExample:
    """Example usage of a tool"""
    params: dict
    description: str
    expected_result: Optional[str] = None


@dataclass
class ToolParameter:
    """Parameter metadata"""
    name: str
    type: str
    required: bool
    description: str
    default: Any = None
    enum_values: Optional[List[str]] = None


@dataclass
class ToolMetadata:
    """Complete metadata for a gateway tool"""
    name: str
    description: str
    parameters: List[ToolParameter]
    scenarios: List[str] = field(default_factory=list)
    examples: List[ToolExample] = field(default_factory=list)
    returns_description: str = ""
    category: str = "general"
    handler: Optional[Callable] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "scenarios": self.scenarios,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "required": p.required,
                    "description": p.description,
                    **({"default": p.default} if p.default is not None else {}),
                    **({"enum": p.enum_values} if p.enum_values else {})
                }
                for p in self.parameters
            ],
            "examples": [
                {
                    "params": e.params,
                    "description": e.description,
                    **({"expected": e.expected_result} if e.expected_result else {})
                }
                for e in self.examples
            ],
            "returns": self.returns_description
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Parameter Schema Builder
# ═══════════════════════════════════════════════════════════════════════════════

def _python_type_to_json_schema(py_type: Type) -> dict:
    """Convert Python type to JSON schema type"""
    origin = get_origin(py_type)
    args = get_args(py_type)

    # Handle Optional[T] = Union[T, None]
    if origin is Union:
        non_none_types = [t for t in args if t is not type(None)]
        if len(non_none_types) == 1:
            schema = _python_type_to_json_schema(non_none_types[0])
            schema["nullable"] = True
            return schema
        return {"anyOf": [_python_type_to_json_schema(t) for t in non_none_types]}

    # Handle List[T]
    if origin is list or origin is List:
        if args:
            return {
                "type": "array",
                "items": _python_type_to_json_schema(args[0])
            }
        return {"type": "array"}

    # Handle Dict[K, V]
    if origin is dict or origin is Dict:
        return {"type": "object"}

    # Handle Enum
    if isinstance(py_type, type) and issubclass(py_type, Enum):
        return {
            "type": "string",
            "enum": [e.value for e in py_type]
        }

    # Basic types
    type_map = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        dict: {"type": "object"},
        list: {"type": "array"},
        Any: {}
    }

    return type_map.get(py_type, {"type": "string"})


def _build_pydantic_model(func: Callable, param_descriptions: Dict[str, str]) -> Type[BaseModel]:
    """Build a Pydantic model from function signature"""
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    fields = {}
    for name, param in sig.parameters.items():
        if name in ('self', 'cls', 'args', 'kwargs'):
            continue

        py_type = type_hints.get(name, str)
        default = param.default if param.default is not inspect.Parameter.empty else ...

        # Create Field with description
        field_kwargs = {"description": param_descriptions.get(name, f"Parameter: {name}")}
        if default is not ...:
            field_kwargs["default"] = default

        fields[name] = (py_type, Field(**field_kwargs))

    # Create dynamic model
    model_name = f"{func.__name__}Params"
    return create_model(model_name, **fields)


def _extract_param_descriptions(func: Callable) -> Dict[str, str]:
    """Extract parameter descriptions from docstring"""
    doc = inspect.getdoc(func) or ""
    descriptions = {}

    # Parse Args/Parameters section
    lines = doc.split('\n')
    in_args = False
    current_param = None

    for line in lines:
        stripped = line.strip()

        # Check for Args/Parameters section
        if stripped.lower() in ('args:', 'parameters:', 'arguments:'):
            in_args = True
            continue

        # End of args section
        if in_args and stripped and not stripped.startswith('-') and ':' not in stripped.split()[0]:
            if not any(stripped.lower().startswith(x) for x in ('returns:', 'return:', 'raises:', 'example:')):
                continue
            in_args = False

        # Parse parameter line
        if in_args:
            # Match patterns like: "name: description" or "- name: description" or "name (type): description"
            match = None
            for pattern in [
                r'^-\s*(\w+)\s*\([^)]*\)?\s*:\s*(.+)$',  # - name (type): desc
                r'^(\w+)\s*\([^)]*\)?\s*:\s*(.+)$',      # name (type): desc
                r'^-\s*(\w+)\s*:\s*(.+)$',               # - name: desc
                r'^(\w+)\s*:\s*(.+)$',                   # name: desc
            ]:
                import re
                m = re.match(pattern, stripped)
                if m:
                    match = m
                    break

            if match:
                param_name = match.group(1)
                description = match.group(2).strip()
                descriptions[param_name] = description

    return descriptions


# ═══════════════════════════════════════════════════════════════════════════════
# Gateway Tool Decorator
# ═══════════════════════════════════════════════════════════════════════════════

# Registry of all gateway tools
_gateway_registry: Dict[str, ToolMetadata] = {}


def gateway_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    scenarios: Optional[List[str]] = None,
    examples: Optional[List[dict]] = None,
    returns: str = "",
    category: str = "general",
    param_descriptions: Optional[Dict[str, str]] = None
):
    """
    Decorator to register a function as a gateway tool.

    Args:
        name: Tool name (defaults to function name)
        description: Tool description (defaults to function docstring)
        scenarios: List of usage scenarios
        examples: List of usage examples, each with "params" and "description"
        returns: Description of return value
        category: Tool category for grouping
        param_descriptions: Override parameter descriptions

    Example:
        @gateway_tool(
            name="queryAlarm",
            scenarios=["When user asks about network alarms"],
            examples=[{"params": {"neName": "NE1"}, "description": "Query alarms for NE1"}]
        )
        def query_alarm(neName: str, alarmType: str = "MUT_LOS") -> dict:
            '''Query alarms from network element'''
            return {"alarms": []}
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_desc = description or (inspect.getdoc(func) or "").split('\n')[0].strip()

        # Extract parameter info
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        doc_descriptions = _extract_param_descriptions(func)
        if param_descriptions:
            doc_descriptions.update(param_descriptions)

        parameters = []
        for param_name, param in sig.parameters.items():
            if param_name in ('self', 'cls', 'args', 'kwargs'):
                continue

            py_type = type_hints.get(param_name, str)
            is_required = param.default is inspect.Parameter.empty
            default = None if is_required else param.default

            # Get type string representation
            type_str = str(py_type).replace('<class ', '').replace('>', '').replace("'", "")

            parameters.append(ToolParameter(
                name=param_name,
                type=type_str,
                required=is_required,
                description=doc_descriptions.get(param_name, f"Parameter: {param_name}"),
                default=default
            ))

        # Parse examples
        tool_examples = []
        if examples:
            for ex in examples:
                tool_examples.append(ToolExample(
                    params=ex.get("params", {}),
                    description=ex.get("description", ""),
                    expected_result=ex.get("expected_result")
                ))

        # Create metadata
        metadata = ToolMetadata(
            name=tool_name,
            description=tool_desc,
            parameters=parameters,
            scenarios=scenarios or [],
            examples=tool_examples,
            returns_description=returns,
            category=category,
            handler=func
        )

        # Register
        _gateway_registry[tool_name] = metadata

        # Mark function
        func._gateway_tool = True
        func._tool_name = tool_name
        func._tool_metadata = metadata

        return func

    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Gateway Class
# ═══════════════════════════════════════════════════════════════════════════════

class ToolGateway:
    """
    Central gateway for invoking registered tools.

    Provides:
    - Tool invocation with parameter validation
    - Tool metadata query
    - Exception handling with structured errors
    """

    def __init__(self):
        self._tools: Dict[str, ToolMetadata] = {}
        self._pydantic_models: Dict[str, Type[BaseModel]] = {}

    def register(self, func: Callable) -> "ToolGateway":
        """Register a function (decorated with @gateway_tool)"""
        if not hasattr(func, '_gateway_tool'):
            raise ValueError(f"Function {func.__name__} must be decorated with @gateway_tool")

        metadata = func._tool_metadata
        self._tools[metadata.name] = metadata

        # Build and cache Pydantic model for validation
        param_descs = {p.name: p.description for p in metadata.parameters}
        self._pydantic_models[metadata.name] = _build_pydantic_model(func, param_descs)

        return self

    def register_module(self, module) -> "ToolGateway":
        """Register all @gateway_tool decorated functions from a module"""
        for name in dir(module):
            obj = getattr(module, name)
            if callable(obj) and hasattr(obj, '_gateway_tool'):
                self.register(obj)
        return self

    def call_tool(self, tool_name: str, params: dict) -> dict:
        """
        Invoke a registered tool with parameter validation.

        Args:
            tool_name: Name of the tool to call
            params: Parameters to pass to the tool

        Returns:
            Structured result dict with "status", "data"/"error", and metadata
        """
        # Check if tool exists
        if tool_name not in self._tools:
            return {
                "status": "error",
                "error": {
                    "type": "tool_not_found",
                    "message": f"Tool '{tool_name}' not found in gateway",
                    "available_tools": list(self._tools.keys())
                },
                "tool": tool_name,
                "params": params
            }

        metadata = self._tools[tool_name]
        handler = metadata.handler

        # Validate parameters
        try:
            model_class = self._pydantic_models.get(tool_name)
            if model_class:
                validated = model_class(**params)
                validated_params = validated.model_dump()
            else:
                validated_params = params
        except ValidationError as e:
            return {
                "status": "error",
                "error": {
                    "type": "validation_error",
                    "message": "Parameter validation failed",
                    "details": json.loads(e.json())
                },
                "tool": tool_name,
                "params": params
            }

        # Execute handler with exception handling
        try:
            result = handler(**validated_params)

            # Normalize result
            if isinstance(result, dict):
                return {
                    "status": "success",
                    "data": result,
                    "tool": tool_name
                }
            else:
                return {
                    "status": "success",
                    "data": {"result": result},
                    "tool": tool_name
                }

        except Exception as e:
            return {
                "status": "error",
                "error": {
                    "type": "execution_error",
                    "message": str(e),
                    "exception_type": type(e).__name__
                },
                "tool": tool_name,
                "params": params
            }

    def get_tool_info(self, tool_name: str) -> Optional[dict]:
        """Get metadata for a specific tool"""
        metadata = self._tools.get(tool_name)
        if metadata:
            return metadata.to_dict()
        return None

    def list_tools(self, category: Optional[str] = None) -> List[dict]:
        """List all registered tools, optionally filtered by category"""
        tools = []
        for name, metadata in self._tools.items():
            if category is None or metadata.category == category:
                tools.append(metadata.to_dict())
        return tools

    def find_tools_for_scenario(self, scenario: str) -> List[dict]:
        """Find tools that match a scenario description"""
        matching = []
        scenario_lower = scenario.lower()

        for metadata in self._tools.values():
            for s in metadata.scenarios:
                if scenario_lower in s.lower() or s.lower() in scenario_lower:
                    matching.append(metadata.to_dict())
                    break

        return matching

    def get_tool_schema(self, tool_name: str) -> Optional[dict]:
        """Get JSON schema for tool parameters"""
        metadata = self._tools.get(tool_name)
        if not metadata:
            return None

        properties = {}
        required = []

        for param in metadata.parameters:
            schema = _python_type_to_json_schema(eval(param.type) if param.type in globals() else str)
            schema["description"] = param.description
            if param.enum_values:
                schema["enum"] = param.enum_values
            properties[param.name] = schema

            if param.required:
                required.append(param.name)

        return {
            "name": tool_name,
            "description": metadata.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# LangChain Tool Integration
# ═══════════════════════════════════════════════════════════════════════════════

# Global gateway instance
_global_gateway = ToolGateway()


def get_global_gateway() -> ToolGateway:
    """Get the global tool gateway instance"""
    return _global_gateway


def _build_gateway_call_tool_docstring() -> str:
    """Dynamically build docstring for gateway_call_tool based on registered tools"""
    gateway = _global_gateway
    tools = gateway.list_tools()

    # Build available tools section
    tools_section = "\n".join([
        f"    - {t['name']}: {t['description']}" +
        (f" (category: {t['category']})" if t.get('category') else "")
        for t in tools
    ])

    # Build examples from tool metadata
    examples_section = ""
    for t in tools[:3]:  # Show first 3 tools as examples
        if t.get('examples'):
            ex = t['examples'][0]
            examples_section += f"""
        {t['name']}:
        {{
            "tool_name": "{t['name']}",
            "params": {json.dumps(ex.get('params', {}), ensure_ascii=False)}
        }}"""

    return f"""Call a tool through the gateway. Use this to invoke any registered tool.

    This is the unified entry point for all gateway-registered tools. You must provide:
    1. tool_name: The exact name of the tool to call (see available tools below)
    2. params: A JSON object containing all required parameters for that tool

    Available Tools ({len(tools)} total):
{tools_section}

    Args:
        tool_name: REQUIRED. Name of the tool to call. Must be one of the available tools listed above.
        params: REQUIRED. Parameters as a JSON object. Must include all required parameters for the tool.
                Use gateway_query_tool with tool_name to see exact parameter requirements.

    Returns:
        JSON string with the tool execution result

    Examples:{examples_section if examples_section else '''
        {{
            "tool_name": "queryAlarmList",
            "params": {{"neName": "NE-001", "alarmType": "MUT_LOS"}}
        }}'''}

    Recommended Workflow:
    1. Use gateway_query_tool {{}} to list all available tools
    2. Use gateway_query_tool {{"tool_name": "xxx"}} to see detailed parameters
    3. Use gateway_call_tool with the correct tool_name and params
    """


def _gateway_call_tool_impl(tool_name: str, params: dict) -> str:
    """Implementation of gateway_call_tool"""
    gateway = _global_gateway

    # Validate required parameters
    if not tool_name or not isinstance(tool_name, str):
        return json.dumps({
            "status": "error",
            "error": {
                "type": "missing_parameter",
                "message": "Missing required parameter: tool_name must be a non-empty string"
            }
        }, ensure_ascii=False)

    if not isinstance(params, dict):
        return json.dumps({
            "status": "error",
            "error": {
                "type": "invalid_parameter_type",
                "message": f"Invalid params type: expected dict, got {type(params).__name__}"
            }
        }, ensure_ascii=False)

    # Check if tool exists
    available_tools = list(gateway._tools.keys())
    if tool_name not in available_tools:
        return json.dumps({
            "status": "error",
            "error": {
                "type": "tool_not_found",
                "message": f"Tool '{tool_name}' not found",
                "available_tools": available_tools,
                "hint": "Use gateway_query_tool to list available tools"
            }
        }, ensure_ascii=False)

    result = gateway.call_tool(tool_name, params)
    return json.dumps(result, ensure_ascii=False, indent=2)


# Create the tool with dynamic docstring
# Use functools.wraps to preserve function metadata
def _create_gateway_call_tool():
    @tool
    def gateway_call_tool(tool_name: str, params: dict) -> str:
        """Call a tool through the gateway."""
        return _gateway_call_tool_impl(tool_name, params)

    # Update docstring after tool registration
    gateway_call_tool.__doc__ = _build_gateway_call_tool_docstring()
    return gateway_call_tool


gateway_call_tool = _create_gateway_call_tool()


def _build_gateway_query_tool_docstring() -> str:
    """Dynamically build docstring for gateway_query_tool based on registered tools"""
    gateway = _global_gateway
    tools = gateway.list_tools()

    # Build tool list for examples
    tool_names = [t['name'] for t in tools[:5]]  # Show first 5 tools
    tool_list_str = ", ".join([f'"{name}"' for name in tool_names])

    # Build category list
    categories = set(t.get('category', 'general') for t in tools)
    category_list = ", ".join([f'"{c}"' for c in categories if c])

    return f"""Query tool metadata from the gateway. Use this to discover available tools and their parameters.

    This tool helps you understand what tools are available and how to use them. You can:
    1. List all available tools ({len(tools)} total)
    2. Get detailed info for a specific tool (parameters, examples, scenarios)
    3. Find tools by scenario/keyword

    Currently Registered Tools:
    {tool_list_str}{"..." if len(tools) > 5 else ""}

    Available Categories:
    {category_list if category_list else "general"}

    Args:
        tool_name: OPTIONAL. Get detailed info for a specific tool by name.
                   Examples: {tool_list_str}
                   Returns: Full metadata including parameters, examples, and usage scenarios.

        scenario: OPTIONAL. Find tools matching a scenario description.
                  Examples: "告警查询", "光功率", "故障分析", "monitor"
                  Returns: List of tools relevant to that scenario.

        category: OPTIONAL. Filter tools by category.
                  Examples: {category_list if category_list else '"general"'}
                  Returns: List of tools in that category.

    Returns:
        JSON string with tool metadata

    Usage Patterns:

    1. List all available tools:
       {{}}

    2. Get detailed info for a specific tool:
       {{"tool_name": "{tool_names[0] if tool_names else "queryAlarmList"}"}}

    3. Find tools by scenario keyword:
       {{"scenario": "告警"}}

    4. List tools in a specific category:
       {{"category": "{list(categories)[0] if categories else "mut_los"}"}}

    Recommended Workflow:
    1. First call with {{}} to see all available tools
    2. Then call with {{"tool_name": "xxx"}} to see detailed parameters
    3. Finally use gateway_call_tool with the correct parameters
    """


def _gateway_query_tool_impl(
    tool_name: Optional[str] = None,
    scenario: Optional[str] = None,
    category: Optional[str] = None
) -> str:
    """Implementation of gateway_query_tool"""
    gateway = _global_gateway

    # Validate that at least one query parameter is provided
    if tool_name is None and scenario is None and category is None:
        # List all tools by default
        tools = gateway.list_tools()
        return json.dumps({
            "status": "success",
            "type": "tool_list",
            "count": len(tools),
            "tools": tools,
            "hint": "Use tool_name parameter to get detailed info for a specific tool"
        }, ensure_ascii=False, indent=2)

    if tool_name:
        if not isinstance(tool_name, str):
            return json.dumps({
                "status": "error",
                "error": {
                    "type": "invalid_parameter",
                    "message": "tool_name must be a string"
                }
            }, ensure_ascii=False)

        info = gateway.get_tool_info(tool_name)
        if info:
            return json.dumps({
                "status": "success",
                "type": "tool_info",
                "data": info
            }, ensure_ascii=False, indent=2)
        else:
            available_tools = list(gateway._tools.keys())
            return json.dumps({
                "status": "error",
                "error": {
                    "type": "tool_not_found",
                    "message": f"Tool '{tool_name}' not found"
                },
                "available_tools": available_tools,
                "hint": "Check the tool name spelling or list all tools"
            }, ensure_ascii=False)

    if scenario:
        tools = gateway.find_tools_for_scenario(scenario)
        return json.dumps({
            "status": "success",
            "type": "tools_for_scenario",
            "scenario": scenario,
            "count": len(tools),
            "tools": tools,
            "hint": "Use tool_name parameter to get detailed info for a specific tool"
        }, ensure_ascii=False, indent=2)

    # List all tools by category
    tools = gateway.list_tools(category)
    return json.dumps({
        "status": "success",
        "type": "tool_list",
        "category": category,
        "count": len(tools),
        "tools": tools,
        "hint": "Use tool_name parameter to get detailed info for a specific tool"
    }, ensure_ascii=False, indent=2)


# Create the tool with dynamic docstring
def _create_gateway_query_tool():
    @tool
    def gateway_query_tool(
        tool_name: Optional[str] = None,
        scenario: Optional[str] = None,
        category: Optional[str] = None
    ) -> str:
        """Query tool metadata from the gateway."""
        return _gateway_query_tool_impl(tool_name, scenario, category)

    # Update docstring after tool registration
    gateway_query_tool.__doc__ = _build_gateway_query_tool_docstring()
    return gateway_query_tool


gateway_query_tool = _create_gateway_query_tool()


# ═══════════════════════════════════════════════════════════════════════════════
# Re-export for convenience
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "gateway_tool",
    "ToolGateway",
    "ToolMetadata",
    "ToolParameter",
    "ToolExample",
    "get_global_gateway",
    "gateway_call_tool",
    "gateway_query_tool",
]
