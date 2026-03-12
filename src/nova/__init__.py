"""
Nova Skill - 轻量级 Skill + Tool 框架
"""

__version__ = "0.1.0"

# 只导出基础模块，避免循环导入
from nova.skill import Skill, SkillRegistry, get_registry

__all__ = ["Skill", "SkillRegistry", "get_registry"]
