"""
Comprehensive tests for Tool Gateway functionality

This module thoroughly tests:
1. Tool registration via @gateway_tool decorator
2. Tool invocation with various parameter types
3. Tool metadata query (detailed info)
4. Tool listing with descriptions
5. Error handling and edge cases
"""

import json
import pytest
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from src.tools.gateway import (
    gateway_tool, ToolGateway, ToolMetadata, ToolParameter, ToolExample,
    get_global_gateway, _gateway_registry
)


# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures and Sample Tools
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def fresh_gateway():
    """Create a fresh gateway instance for isolated tests"""
    return ToolGateway()


@pytest.fixture
def sample_tools_module():
    """Create a module-like object with sample tools"""
    # Clear any existing registrations
    _gateway_registry.clear()

    @gateway_tool(
        name="simpleTool",
        description="A simple tool with basic parameters",
        scenarios=["When you need to do something simple"],
        examples=[
            {"params": {"name": "test"}, "description": "Basic usage"}
        ],
        returns="A greeting message",
        category="test"
    )
    def simple_tool(name: str, count: int = 1) -> str:
        """Simple tool for testing

        Args:
            name: The name to greet
            count: How many times to greet

        Returns:
            A greeting string
        """
        return f"Hello {name}! " * count

    @gateway_tool(
        name="complexTool",
        description="A tool with complex parameter types",
        scenarios=["When you need complex data processing"],
        examples=[
            {"params": {"items": ["a", "b"], "config": {"key": "value"}}, "description": "With list and dict"}
        ],
        returns="Processed data",
        category="test"
    )
    def complex_tool(
        items: List[str],
        config: Dict[str, Any],
        optional_flag: Optional[bool] = None
    ) -> dict:
        """Complex tool with various types

        Args:
            items: List of items to process
            config: Configuration dictionary
            optional_flag: Optional boolean flag

        Returns:
            Processed result
        """
        return {
            "processed": len(items),
            "config_keys": list(config.keys()),
            "flag": optional_flag
        }

    @gateway_tool(
        name="errorTool",
        description="A tool that always raises an exception",
        scenarios=["Testing error handling"],
        category="test"
    )
    def error_tool(should_fail: bool = True) -> str:
        """Tool that raises exceptions

        Args:
            should_fail: Whether to raise an exception
        """
        if should_fail:
            raise ValueError("Intentional error for testing")
        return "Success"

    # Return the decorated functions
    return {
        "simple_tool": simple_tool,
        "complex_tool": complex_tool,
        "error_tool": error_tool
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Test Class 1: Tool Registration
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolRegistration:
    """Test tool registration via @gateway_tool decorator"""

    def test_decorator_registers_to_global_registry(self, sample_tools_module):
        """Test that @gateway_tool registers to global registry"""
        # Check global registry has tools
        assert "simpleTool" in _gateway_registry
        assert "complexTool" in _gateway_registry
        assert "errorTool" in _gateway_registry

    def test_decorator_creates_correct_metadata(self, sample_tools_module):
        """Test that decorator creates correct metadata"""
        metadata = _gateway_registry["simpleTool"]

        assert isinstance(metadata, ToolMetadata)
        assert metadata.name == "simpleTool"
        assert metadata.description == "A simple tool with basic parameters"
        assert metadata.category == "test"
        assert len(metadata.scenarios) == 1
        assert metadata.scenarios[0] == "When you need to do something simple"
        assert len(metadata.examples) == 1
        assert metadata.examples[0].params == {"name": "test"}
        assert metadata.returns_description == "A greeting message"

    def test_decorator_extracts_parameters(self, sample_tools_module):
        """Test that decorator correctly extracts parameter info"""
        metadata = _gateway_registry["simpleTool"]

        assert len(metadata.parameters) == 2

        # Check first parameter
        param1 = metadata.parameters[0]
        assert param1.name == "name"
        assert param1.required == True
        assert "name" in param1.description.lower()

        # Check second parameter with default
        param2 = metadata.parameters[1]
        assert param2.name == "count"
        assert param2.required == False
        assert param2.default == 1

    def test_decorator_extracts_complex_parameters(self, sample_tools_module):
        """Test parameter extraction for complex types"""
        metadata = _gateway_registry["complexTool"]

        assert len(metadata.parameters) == 3

        # List parameter
        items_param = [p for p in metadata.parameters if p.name == "items"][0]
        assert items_param.required == True
        assert "list" in items_param.type.lower() or "List" in items_param.type

        # Dict parameter
        config_param = [p for p in metadata.parameters if p.name == "config"][0]
        assert config_param.required == True
        assert "dict" in config_param.type.lower() or "Dict" in config_param.type

        # Optional parameter
        flag_param = [p for p in metadata.parameters if p.name == "optional_flag"][0]
        assert flag_param.required == False
        assert flag_param.default is None

    def test_decorator_preserves_function(self, sample_tools_module):
        """Test that the original function is preserved and callable"""
        simple_tool = sample_tools_module["simple_tool"]

        # Should be callable directly
        result = simple_tool(name="World", count=2)
        assert result == "Hello World! Hello World! "

    def test_decorator_marks_function(self, sample_tools_module):
        """Test that decorator marks function with metadata"""
        simple_tool = sample_tools_module["simple_tool"]

        assert hasattr(simple_tool, '_gateway_tool')
        assert simple_tool._gateway_tool == True
        assert hasattr(simple_tool, '_tool_name')
        assert simple_tool._tool_name == "simpleTool"
        assert hasattr(simple_tool, '_tool_metadata')


# ═══════════════════════════════════════════════════════════════════════════════
# Test Class 2: Gateway Registration
# ═══════════════════════════════════════════════════════════════════════════════

class TestGatewayRegistration:
    """Test ToolGateway class registration methods"""

    def test_register_single_tool(self, fresh_gateway, sample_tools_module):
        """Test registering a single tool"""
        gateway = fresh_gateway
        simple_tool = sample_tools_module["simple_tool"]

        gateway.register(simple_tool)

        assert "simpleTool" in gateway._tools
        assert gateway._tools["simpleTool"].name == "simpleTool"

    def test_register_builds_pydantic_model(self, fresh_gateway, sample_tools_module):
        """Test that registration builds Pydantic validation model"""
        gateway = fresh_gateway
        simple_tool = sample_tools_module["simple_tool"]

        gateway.register(simple_tool)

        assert "simpleTool" in gateway._pydantic_models
        model = gateway._pydantic_models["simpleTool"]
        # Should be able to validate
        instance = model(name="test", count=3)
        assert instance.name == "test"
        assert instance.count == 3

    def test_register_rejects_non_decorated(self, fresh_gateway):
        """Test that register rejects non-decorated functions"""
        gateway = fresh_gateway

        def normal_function():
            pass

        with pytest.raises(ValueError, match="must be decorated with @gateway_tool"):
            gateway.register(normal_function)

    def test_register_module(self, fresh_gateway, sample_tools_module):
        """Test registering all tools from a module-like object"""
        gateway = fresh_gateway

        # Create a mock module
        class MockModule:
            pass

        module = MockModule()
        for name, func in sample_tools_module.items():
            setattr(module, name, func)

        gateway.register_module(module)

        assert len(gateway._tools) == 3
        assert "simpleTool" in gateway._tools
        assert "complexTool" in gateway._tools
        assert "errorTool" in gateway._tools


# ═══════════════════════════════════════════════════════════════════════════════
# Test Class 3: Tool Invocation
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolInvocation:
    """Test tool invocation via gateway.call_tool()"""

    def test_call_simple_tool(self, fresh_gateway, sample_tools_module):
        """Test calling a simple tool"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["simple_tool"])

        result = gateway.call_tool("simpleTool", {"name": "Alice", "count": 2})

        assert result["status"] == "success"
        assert result["tool"] == "simpleTool"
        # Result is wrapped in {"result": ...} for non-dict returns
        assert "Hello Alice! Hello Alice!" in result["data"]["result"]

    def test_call_with_default_params(self, fresh_gateway, sample_tools_module):
        """Test calling with default parameter values"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["simple_tool"])

        # Only provide required param
        result = gateway.call_tool("simpleTool", {"name": "Bob"})

        assert result["status"] == "success"
        # Should use default count=1, result is wrapped in {"result": ...}
        assert result["data"]["result"] == "Hello Bob! "

    def test_call_complex_tool(self, fresh_gateway, sample_tools_module):
        """Test calling tool with complex types"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["complex_tool"])

        result = gateway.call_tool("complexTool", {
            "items": ["x", "y", "z"],
            "config": {"mode": "fast", "debug": True}
        })

        assert result["status"] == "success"
        assert result["data"]["processed"] == 3
        assert "mode" in result["data"]["config_keys"]
        assert result["data"]["flag"] is None

    def test_call_nonexistent_tool(self, fresh_gateway):
        """Test calling a tool that doesn't exist"""
        gateway = fresh_gateway

        result = gateway.call_tool("nonexistent", {})

        assert result["status"] == "error"
        assert result["error"]["type"] == "tool_not_found"
        assert "nonexistent" in result["error"]["message"]
        assert "available_tools" in result["error"]

    def test_call_missing_required_param(self, fresh_gateway, sample_tools_module):
        """Test calling with missing required parameter"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["simple_tool"])

        result = gateway.call_tool("simpleTool", {})  # Missing 'name'

        assert result["status"] == "error"
        assert result["error"]["type"] == "validation_error"
        assert "details" in result["error"]

    def test_call_wrong_param_type(self, fresh_gateway, sample_tools_module):
        """Test calling with wrong parameter type"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["simple_tool"])

        result = gateway.call_tool("simpleTool", {"name": "test", "count": "not_a_number"})

        assert result["status"] == "error"
        assert result["error"]["type"] == "validation_error"

    def test_call_tool_execution_error(self, fresh_gateway, sample_tools_module):
        """Test handling of execution errors"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["error_tool"])

        result = gateway.call_tool("errorTool", {"should_fail": True})

        assert result["status"] == "error"
        assert result["error"]["type"] == "execution_error"
        assert "Intentional error" in result["error"]["message"]
        assert result["error"]["exception_type"] == "ValueError"

    def test_call_tool_success_after_error(self, fresh_gateway, sample_tools_module):
        """Test that gateway continues to work after an error"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["error_tool"])
        gateway.register(sample_tools_module["simple_tool"])

        # First call - error
        result1 = gateway.call_tool("errorTool", {})
        assert result1["status"] == "error"

        # Second call - should still work
        result2 = gateway.call_tool("simpleTool", {"name": "Test"})
        assert result2["status"] == "success"


# ═══════════════════════════════════════════════════════════════════════════════
# Test Class 4: Tool Metadata Query
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolMetadataQuery:
    """Test querying tool metadata"""

    def test_get_tool_info(self, fresh_gateway, sample_tools_module):
        """Test getting detailed info for a tool"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["simple_tool"])

        info = gateway.get_tool_info("simpleTool")

        assert info is not None
        assert info["name"] == "simpleTool"
        assert info["description"] == "A simple tool with basic parameters"
        assert info["category"] == "test"
        assert "scenarios" in info
        assert "parameters" in info
        assert "examples" in info
        assert "returns" in info

    def test_get_tool_info_not_found(self, fresh_gateway):
        """Test getting info for non-existent tool"""
        gateway = fresh_gateway

        info = gateway.get_tool_info("nonexistent")

        assert info is None

    def test_get_tool_info_structure(self, fresh_gateway, sample_tools_module):
        """Test the structure of tool info"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["complex_tool"])

        info = gateway.get_tool_info("complexTool")

        # Check parameters structure
        params = info["parameters"]
        assert len(params) == 3

        for param in params:
            assert "name" in param
            assert "type" in param
            assert "required" in param
            assert "description" in param

        # Check examples structure
        examples = info["examples"]
        assert len(examples) == 1
        assert "params" in examples[0]
        assert "description" in examples[0]

    def test_list_all_tools(self, fresh_gateway, sample_tools_module):
        """Test listing all registered tools"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["simple_tool"])
        gateway.register(sample_tools_module["complex_tool"])

        tools = gateway.list_tools()

        assert len(tools) == 2
        tool_names = [t["name"] for t in tools]
        assert "simpleTool" in tool_names
        assert "complexTool" in tool_names

    def test_list_tools_by_category(self, fresh_gateway, sample_tools_module):
        """Test filtering tools by category"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["simple_tool"])

        # Same category
        tools = gateway.list_tools(category="test")
        assert len(tools) == 1

        # Different category
        tools = gateway.list_tools(category="other")
        assert len(tools) == 0

    def test_find_tools_by_scenario(self, fresh_gateway, sample_tools_module):
        """Test finding tools by scenario"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["simple_tool"])
        gateway.register(sample_tools_module["complex_tool"])

        # Search for "simple" - should match simpleTool
        tools = gateway.find_tools_for_scenario("simple")
        assert len(tools) >= 1
        tool_names = [t["name"] for t in tools]
        assert "simpleTool" in tool_names

        # Search for "complex" - should match complexTool
        tools = gateway.find_tools_for_scenario("complex")
        assert len(tools) >= 1
        tool_names = [t["name"] for t in tools]
        assert "complexTool" in tool_names

    def test_find_tools_no_match(self, fresh_gateway, sample_tools_module):
        """Test scenario search with no matches"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["simple_tool"])

        tools = gateway.find_tools_for_scenario("nonexistent scenario")
        assert len(tools) == 0

    def test_get_tool_schema(self, fresh_gateway, sample_tools_module):
        """Test getting JSON schema for tool"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["simple_tool"])

        schema = gateway.get_tool_schema("simpleTool")

        assert schema is not None
        assert schema["name"] == "simpleTool"
        assert "parameters" in schema
        assert schema["parameters"]["type"] == "object"
        assert "properties" in schema["parameters"]
        assert "required" in schema["parameters"]
        assert "name" in schema["parameters"]["required"]


# ═══════════════════════════════════════════════════════════════════════════════
# Test Class 5: Integration with MUT_LOS Tools
# ═══════════════════════════════════════════════════════════════════════════════

class TestMutLosToolsIntegration:
    """Test integration with actual MUT_LOS tools"""

    def test_mut_los_tools_registered(self):
        """Test that MUT_LOS tools are auto-registered"""
        from src.tools import mut_los_tools

        gateway = get_global_gateway()
        tools = gateway.list_tools(category="mut_los")

        assert len(tools) >= 9

        tool_names = [t["name"] for t in tools]
        assert "queryAlarmList" in tool_names
        assert "queryFaultSegment" in tool_names
        assert "queryPortOpticalPower" in tool_names

    def test_mut_los_tool_has_scenarios(self):
        """Test that MUT_LOS tools have usage scenarios"""
        gateway = get_global_gateway()

        info = gateway.get_tool_info("queryAlarmList")

        assert info is not None
        assert len(info["scenarios"]) > 0
        assert any("MUT_LOS" in s or "alarm" in s.lower() for s in info["scenarios"])

    def test_mut_los_tool_has_examples(self):
        """Test that MUT_LOS tools have usage examples"""
        gateway = get_global_gateway()

        info = gateway.get_tool_info("queryAlarmList")

        assert info is not None
        assert len(info["examples"]) > 0
        assert "params" in info["examples"][0]
        assert "description" in info["examples"][0]

    def test_mut_los_tool_invocation(self):
        """Test invoking an actual MUT_LOS tool"""
        gateway = get_global_gateway()

        result = gateway.call_tool("queryAlarmList", {
            "neName": "TEST-NE-001",
            "alarmType": "MUT_LOS"
        })

        assert result["status"] == "success"
        assert result["tool"] == "queryAlarmList"
        assert "data" in result
        assert "code" in result["data"]
        assert result["data"]["code"] == 0

    def test_mut_los_tool_chain(self):
        """Test chaining multiple MUT_LOS tool calls"""
        gateway = get_global_gateway()

        # Step 1: Query alarms
        alarms_result = gateway.call_tool("queryAlarmList", {"neName": "NE-001"})
        assert alarms_result["status"] == "success"

        # Step 2: Get fault sequence number
        fault_seq_result = gateway.call_tool("queryFaultSeqNo", {"eventId": "EVT-001"})
        assert fault_seq_result["status"] == "success"

        # Step 3: Query fault segment
        fault_seq_no = fault_seq_result["data"]["data"]["faultSeqNo"]
        segment_result = gateway.call_tool("queryFaultSegment", {"faultSeqNo": fault_seq_no})
        assert segment_result["status"] == "success"


# ═══════════════════════════════════════════════════════════════════════════════
# Test Class 6: LangChain Tool Interface
# ═══════════════════════════════════════════════════════════════════════════════

class TestLangChainInterface:
    """Test LangChain tool integration"""

    def test_gateway_call_tool_is_registered(self):
        """Test that gateway_call_tool is in the tools list"""
        from src.tools import get_all_tools

        tools = get_all_tools()
        tool_names = [t.name for t in tools]

        assert "gateway_call_tool" in tool_names
        assert "gateway_query_tool" in tool_names

    def test_gateway_call_tool_invocation(self):
        """Test invoking via LangChain tool interface"""
        from src.tools import gateway_call_tool

        result = gateway_call_tool.invoke({
            "tool_name": "queryAlarmList",
            "params": {"neName": "NE-TEST"}
        })

        # Result should be JSON string
        data = json.loads(result)
        assert data["status"] == "success"
        assert data["tool"] == "queryAlarmList"

    def test_gateway_query_tool_invocation(self):
        """Test querying via LangChain tool interface"""
        from src.tools import gateway_query_tool

        result = gateway_query_tool.invoke({"tool_name": "queryAlarmList"})

        data = json.loads(result)
        assert data["status"] == "success"
        assert data["type"] == "tool_info"
        assert data["data"]["name"] == "queryAlarmList"

    def test_gateway_query_tool_list_all(self):
        """Test listing all tools via LangChain interface"""
        from src.tools import gateway_query_tool

        result = gateway_query_tool.invoke({})

        data = json.loads(result)
        assert data["status"] == "success"
        assert data["type"] == "tool_list"
        assert data["count"] >= 9  # At least 9 MUT_LOS tools


# ═══════════════════════════════════════════════════════════════════════════════
# Test Class 7: Edge Cases and Error Handling
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Test edge cases and error scenarios"""

    def test_empty_params(self, fresh_gateway, sample_tools_module):
        """Test calling with empty params dict"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["simple_tool"])

        result = gateway.call_tool("simpleTool", {})

        assert result["status"] == "error"
        assert result["error"]["type"] == "validation_error"

    def test_extra_params(self, fresh_gateway, sample_tools_module):
        """Test calling with extra unused parameters"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["simple_tool"])

        # Pydantic should ignore extra by default
        result = gateway.call_tool("simpleTool", {
            "name": "Test",
            "extra_param": "ignored"
        })

        # Should succeed (extra params ignored)
        assert result["status"] == "success"

    def test_none_for_optional(self, fresh_gateway, sample_tools_module):
        """Test passing None for optional parameters"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["complex_tool"])

        result = gateway.call_tool("complexTool", {
            "items": ["a"],
            "config": {},
            "optional_flag": None
        })

        assert result["status"] == "success"

    def test_unicode_parameters(self, fresh_gateway, sample_tools_module):
        """Test handling of unicode in parameters"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["simple_tool"])

        result = gateway.call_tool("simpleTool", {"name": "测试中文"})

        assert result["status"] == "success"
        # Result is wrapped in {"result": ...}
        assert "测试中文" in result["data"]["result"]

    def test_large_params(self, fresh_gateway, sample_tools_module):
        """Test with large parameter values"""
        gateway = fresh_gateway
        gateway.register(sample_tools_module["complex_tool"])

        large_list = [f"item_{i}" for i in range(1000)]
        result = gateway.call_tool("complexTool", {
            "items": large_list,
            "config": {"key": "x" * 10000}
        })

        assert result["status"] == "success"
        assert result["data"]["processed"] == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
