"""
Nova Skill - 轻量级 Skill + Tool 框架

使用 LangChain / LangGraph 框架能力
支持跨平台（Windows / Linux / macOS）
"""

__version__ = "0.1.0"

from nova.skill import Skill, SkillRegistry
from nova.agent import Agent

__all__ = ["Skill", "SkillRegistry", "Agent"]
