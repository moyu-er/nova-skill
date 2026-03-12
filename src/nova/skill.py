"""
Skill 模块 - Markdown SKILL.md 格式

跨平台路径处理，支持 Windows/Linux/macOS
"""
import re
from dataclasses import dataclass, field
from typing import List, Callable, Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    func: Callable = None
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Skill:
    """Skill 定义"""
    name: str
    description: str = ""
    system_prompt: str = ""
    full_content: str = ""  # 完整 SKILL.md 内容
    tools: List[Tool] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    skill_path: Path = None  # 跨平台路径


class SkillRegistry:
    """Skill 注册中心"""
    
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
        """列出所有 skill 名称（用于工具）"""
        return list(self._skills.keys())
    
    def read_skill_content(self, skill_name: str) -> str:
        """
        读取 skill 完整内容（工具函数）
        让模型能够按需读取 skill 的详细内容
        """
        skill = self._skills.get(skill_name)
        if not skill:
            return f"Skill '{skill_name}' not found. Available: {self.list_skill_names()}"
        
        if skill.skill_path:
            try:
                content = skill.skill_path.read_text(encoding='utf-8')
                return content
            except Exception as e:
                logger.error(f"Failed to read skill {skill_name}: {e}")
                return f"Error reading skill: {e}"
        
        return skill.full_content or "No content available"
    
    def load_from_directory(self, skills_dir: Path) -> List[Skill]:
        """从目录加载所有 skill"""
        skills = []
        
        # 跨平台路径处理
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
        """从单个目录加载 skill"""
        skill_md = skill_dir / "SKILL.md"
        
        if not skill_md.exists():
            return None
        
        try:
            content = skill_md.read_text(encoding='utf-8')
            return self._parse_markdown(content, skill_dir.name, skill_md)
        except Exception as e:
            logger.error(f"Failed to load skill from {skill_dir}: {e}")
            return None
    
    def _parse_markdown(self, content: str, name: str, skill_path: Path) -> Skill:
        """解析 Markdown 内容"""
        
        # 提取描述
        description = ""
        lines = content.split('\n')
        desc_lines = []
        in_desc = False
        for line in lines:
            if line.startswith('## '):
                break
            if line.strip():
                in_desc = True
            elif in_desc and not line.strip():
                break
            if in_desc:
                desc_lines.append(line)
        if desc_lines:
            description = '\n'.join(desc_lines).strip()
        
        # 提取能力标签
        capabilities = []
        cap_match = re.search(r'## 能力标签\s*\n+((?:- .+\n)+)', content, re.MULTILINE)
        if cap_match:
            caps_text = cap_match.group(1)
            capabilities = [c.strip('- ').strip() for c in caps_text.split('\n') if c.strip()]
        if not capabilities:
            capabilities = [name]
        
        # 构建 system_prompt
        system_prompt = self._build_system_prompt(content, description)
        
        return Skill(
            name=name,
            description=description,
            system_prompt=system_prompt,
            full_content=content,
            capabilities=capabilities,
            skill_path=skill_path
        )
    
    def _build_system_prompt(self, content: str, description: str) -> str:
        """构建 system prompt"""
        parts = []
        
        if description:
            parts.append(description)
        
        # 代码规范
        code_spec = re.search(r'## 代码规范\s*\n+([\s\S]*?)(?=\n## |\n### |\Z)', content, re.MULTILINE)
        if code_spec:
            parts.append("\n## 代码规范\n" + code_spec.group(1).strip())
        
        # 输出格式
        output = re.search(r'## 输出格式\s*\n+([\s\S]*?)(?=\n## |\n### |\Z)', content, re.MULTILINE)
        if output:
            parts.append("\n## 输出格式\n" + output.group(1).strip())
        
        # 注意事项
        notes = re.search(r'## 注意事项\s*\n+([\s\S]*?)(?=\n## |\n### |\Z)', content, re.MULTILINE)
        if notes:
            parts.append("\n## 注意事项\n" + notes.group(1).strip())
        
        return "\n\n".join(parts)


# 全局注册表
_global_registry = None


def get_registry() -> SkillRegistry:
    """获取全局技能注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry
