"""
Skill Tools - Skill registry operations
"""
from typing import Annotated

from langchain_core.tools import tool

from . import get_global_registry


@tool
def get_available_skills() -> str:
    """Get list of all available skills"""
    registry = get_global_registry()
    skills = registry.list_all()

    if not skills:
        return "No skills available"

    result = []
    for skill in skills:
        desc = f" - {skill.description}" if skill.description else ""
        result.append(f"- {skill.name}{desc}")

    return "Available skills:\n" + "\n".join(result)


@tool
def read_skill_detail(skill_name: Annotated[str, "Name of the skill to read"]) -> str:
    """
    Read detailed content of a specific skill.

    Use this to get full skill instructions when you need to use a skill.
    """
    registry = get_global_registry()
    skill = registry.get(skill_name)

    if not skill:
        available = [s.name for s in registry.list_all()]
        return f"Skill '{skill_name}' not found. Available: {available}"

    return f"# {skill.name}\n\n{skill.content}"
