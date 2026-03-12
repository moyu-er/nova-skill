"""
Skill module - Supports YAML frontmatter format

Reference: openskills implementation
"""
import re
from dataclasses import dataclass, field
from typing import List, Callable, Dict, Any, Optional
from pathlib import Path
import logging
import yaml

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """Tool definition"""
    name: str
    description: str
    func: Callable = None
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Skill:
    """Skill definition"""
    name: str
    description: str = ""
    # content is the markdown content after YAML frontmatter
    content: str = ""
    # full_content is the complete SKILL.md content
    full_content: str = ""
    # metadata is the metadata from YAML frontmatter
    metadata: Dict[str, Any] = field(default_factory=dict)
    tools: List[Tool] = field(default_factory=list)
    skill_path: Path = None  # Cross-platform path


class SkillRegistry:
    """Skill registry"""
    
    def __init__(self, skills_dir: Path = None):
        self._skills: Dict[str, Skill] = {}
        self.skills_dir = skills_dir
        if skills_dir:
            self.load_from_directory(skills_dir)
    
    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")
    
    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)
    
    def list_all(self) -> List[Skill]:
        return list(self._skills.values())
    
    def list_skill_names(self) -> List[str]:
        """List all skill names (for tools)"""
        return list(self._skills.keys())
    
    def read_skill_content(self, skill_name: str) -> str:
        """
        Read skill full content (tool function)
        Returns markdown content after YAML frontmatter
        """
        skill = self._skills.get(skill_name)
        if not skill:
            return f"Skill '{skill_name}' not found. Available: {self.list_skill_names()}"
        
        # Return content (markdown content after YAML frontmatter)
        return skill.content or "No content available"
    
    def load_from_directory(self, skills_dir: Path) -> List[Skill]:
        """Load all skills from directory"""
        skills = []
        
        # Cross-platform path handling
        skills_dir = Path(skills_dir).resolve()
        
        if not skills_dir.exists():
            logger.warning(f"Skills directory not found: {skills_dir}")
            return skills
        
        logger.info(f"Loading skills from: {skills_dir}")
        
        for skill_path in skills_dir.iterdir():
            if skill_path.is_dir():
                skill = self._load_skill_from_dir(skill_path)
                if skill:
                    self.register(skill)
                    skills.append(skill)
        
        return skills
    
    def _load_skill_from_dir(self, skill_dir: Path) -> Optional[Skill]:
        """Load skill from single directory"""
        skill_md = skill_dir / "SKILL.md"
        
        if not skill_md.exists():
            return None
        
        try:
            content = skill_md.read_text(encoding='utf-8')
            return self._parse_skill(content, skill_dir.name, skill_md)
        except Exception as e:
            logger.error(f"Failed to load skill from {skill_dir}: {e}")
            return None
    
    def _parse_skill(self, content: str, name: str, skill_path: Path) -> Skill:
        """Parse SKILL.md content (supports YAML frontmatter)"""
        
        # Parse YAML frontmatter
        frontmatter = {}
        body_content = content
        
        if content.strip().startswith('---'):
            # Extract frontmatter
            match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
            if match:
                frontmatter_text = match.group(1)
                body_content = match.group(2)
                frontmatter = yaml.safe_load(frontmatter_text) or {}
        
        # Get name and description from frontmatter
        skill_name = frontmatter.get('name', name)
        description = frontmatter.get('description', '')
        
        return Skill(
            name=skill_name,
            description=description,
            content=body_content.strip(),
            full_content=content,
            metadata=frontmatter.get('metadata', {}),
            skill_path=skill_path
        )


# Global registry
_global_registry = None


def get_registry() -> SkillRegistry:
    """Get global skill registry"""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry
