"""
Skill 模块 - Markdown 格式 Skill 定义

解析 SKILL.md 文件：
- 描述 → system_prompt 的一部分
- 能力标签 → 用于匹配 Agent
- 代码规范 → system_prompt
- 输出格式 → system_prompt  
- 注意事项 → system_prompt
- 代码示例 → few-shot examples
"""
from dataclasses import dataclass, field
from typing import List, Callable, Dict, Any, Optional
from pathlib import Path
import re


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    func: Optional[Callable] = None
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Skill:
    """Skill 定义"""
    name: str
    description: str
    system_prompt: str  # 完整的系统提示词
    capabilities: List[str]  # 能力标签
    tools: List[Tool] = field(default_factory=list)
    examples: List[Dict[str, str]] = field(default_factory=list)  # 代码示例


class SkillLoader:
    """从 Markdown 文件加载 Skill"""
    
    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
    
    def load_all(self) -> List[Skill]:
        """加载所有 skills"""
        skills = []
        
        if not self.skills_dir.exists():
            print(f"[SkillLoader] Directory not found: {self.skills_dir}")
            return skills
        
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    try:
                        skill = self._parse_skill(skill_md, skill_dir.name)
                        skills.append(skill)
                        print(f"[SkillLoader] Loaded: {skill.name}")
                    except Exception as e:
                        print(f"[SkillLoader] Failed to load {skill_dir.name}: {e}")
        
        return skills
    
    def _parse_skill(self, md_path: Path, skill_name: str) -> Skill:
        """解析 SKILL.md 文件"""
        content = md_path.read_text(encoding='utf-8')
        
        # 提取标题（第一个 # 后面的内容）
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else skill_name
        
        # 提取描述（## 描述 后面的内容）
        desc = self._extract_section(content, '描述')
        
        # 提取能力标签
        caps = self._extract_list(content, '能力标签')
        
        # 提取代码规范
        code_spec = self._extract_section(content, '代码规范')
        
        # 提取输出格式
        output_fmt = self._extract_section(content, '输出格式')
        
        # 提取注意事项
        notes = self._extract_section(content, '注意事项')
        
        # 提取代码示例
        examples = self._extract_code_examples(content)
        
        # 构建 system_prompt
        system_prompt = self._build_system_prompt(
            title=title,
            description=desc,
            code_spec=code_spec,
            output_fmt=output_fmt,
            notes=notes
        )
        
        return Skill(
            name=skill_name,
            description=desc or title,
            system_prompt=system_prompt,
            capabilities=caps if caps else [skill_name],
            tools=[],  # 工具需要外部绑定
            examples=examples
        )
    
    def _extract_section(self, content: str, section_name: str) -> str:
        """提取 ## 章节内容"""
        pattern = rf'##\s*{section_name}\s*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""
    
    def _extract_list(self, content: str, section_name: str) -> List[str]:
        """提取列表（如能力标签）"""
        section = self._extract_section(content, section_name)
        items = []
        for line in section.split('\n'):
            line = line.strip()
            if line.startswith('- ') or line.startswith('* '):
                items.append(line[2:].strip())
        return items
    
    def _extract_code_examples(self, content: str) -> List[Dict[str, str]]:
        """提取代码示例"""
        examples = []
        
        # 找到 ## 代码示例 部分
        examples_section = self._extract_section(content, '代码示例')
        if not examples_section:
            return examples
        
        # 提取代码块
        code_blocks = re.findall(r'```(\w+)?\n(.*?)```', examples_section, re.DOTALL)
        for i, (lang, code) in enumerate(code_blocks):
            if len(code.strip()) > 50:
                examples.append({
                    "title": f"示例 {i+1}",
                    "code": code.strip(),
                    "language": lang or "python"
                })
        
        return examples
    
    def _build_system_prompt(
        self,
        title: str,
        description: str,
        code_spec: str,
        output_fmt: str,
        notes: str
    ) -> str:
        """构建完整的 system_prompt"""
        parts = [f"# {title}"]
        
        if description:
            parts.append(f"\n## 描述\n{description}")
        
        if code_spec:
            parts.append(f"\n## 代码规范\n{code_spec}")
        
        if output_fmt:
            parts.append(f"\n## 输出格式\n{output_fmt}")
        
        if notes:
            parts.append(f"\n## 注意事项\n{notes}")
        
        return "\n\n".join(parts)


class SkillRegistry:
    """Skill 注册中心"""
    
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
    
    def register(self, skill: Skill) -> None:
        """注册 skill"""
        self._skills[skill.name] = skill
    
    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)
    
    def list_all(self) -> List[Skill]:
        return list(self._skills.values())
    
    def find_by_capability(self, capability: str) -> List[Skill]:
        """根据能力标签查找"""
        return [s for s in self._skills.values() if capability in s.capabilities]
    
    def load_from_directory(self, skills_dir: Path) -> List[Skill]:
        """从目录加载所有 skills"""
        loader = SkillLoader(skills_dir)
        skills = loader.load_all()
        for skill in skills:
            self.register(skill)
        return skills
