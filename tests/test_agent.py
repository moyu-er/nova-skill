"""
Agent module tests - 测试 AgentConfig 和 ModelType 集成
"""

import pytest
from src import ModelType
from src import AgentConfig


class TestAgentConfig:
    """测试 AgentConfig 配置类"""

    def test_default_config(self):
        """测试默认配置"""
        config = AgentConfig()
        assert config.name == "nova"
        assert config.model == "gpt-4o-mini"
        assert config.temperature == 0.7
        assert config.model_type == ModelType.AUTO
        assert config.skills == []

    def test_config_with_model_type_enum(self):
        """测试使用 ModelType 枚举创建配置"""
        config = AgentConfig(
            name="test",
            model="gpt-4o",
            model_type=ModelType.OPENAI,
            skills=["coder"]
        )
        assert config.name == "test"
        assert config.model == "gpt-4o"
        assert config.model_type == ModelType.OPENAI
        assert config.skills == ["coder"]

    def test_config_with_model_type_string(self):
        """测试使用字符串创建配置（自动转换）"""
        config = AgentConfig(
            model_type="anthropic"
        )
        assert config.model_type == ModelType.ANTHROPIC

    def test_config_is_anthropic_with_enum(self):
        """测试 is_anthropic 属性 - 使用枚举"""
        config = AgentConfig(model_type=ModelType.ANTHROPIC)
        assert config.is_anthropic is True
        assert config.is_openai is False

    def test_config_is_openai_with_enum(self):
        """测试 is_openai 属性 - 使用枚举"""
        config = AgentConfig(model_type=ModelType.OPENAI)
        assert config.is_openai is True
        assert config.is_anthropic is False

    def test_config_auto_detect_anthropic(self):
        """测试自动检测 Anthropic 模型"""
        config = AgentConfig(
            model_type=ModelType.AUTO,
            model="claude-3-5-sonnet-20241022"
        )
        assert config.is_anthropic is True
        assert config.is_openai is False

    def test_config_auto_detect_openai(self):
        """测试自动检测 OpenAI 模型"""
        config = AgentConfig(
            model_type=ModelType.AUTO,
            model="gpt-4o"
        )
        assert config.is_openai is True
        assert config.is_anthropic is False

    def test_config_auto_detect_from_model_name(self):
        """测试从模型名称自动检测类型"""
        # Claude 模型
        config_claude = AgentConfig(model="claude-3-opus")
        assert config_claude.is_anthropic is True

        # GPT 模型
        config_gpt = AgentConfig(model="gpt-4")
        assert config_gpt.is_openai is True


class TestModelTypeIntegration:
    """测试 ModelType 与 AgentConfig 的集成"""

    def test_model_type_in_config_serialization(self):
        """测试配置中的 ModelType 序列化"""
        config = AgentConfig(model_type=ModelType.OPENAI)
        # 验证可以获取字符串值
        assert config.model_type.value == "openai"

    def test_model_type_comparison_in_config(self):
        """测试配置中的 ModelType 比较"""
        config = AgentConfig(model_type=ModelType.ANTHROPIC)
        assert config.model_type == ModelType.ANTHROPIC
        assert config.model_type != ModelType.OPENAI


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
