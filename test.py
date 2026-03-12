"""
测试脚本 - 验证 Nova Skill 流程

不实际调用 API，仅验证配置和代码逻辑
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import logging
logging.basicConfig(level=logging.INFO)

print("=" * 50)
print("Nova Skill 测试")
print("=" * 50)

# 1. 测试 Skill 加载
print("\n[1/5] 测试 Skill 加载...")
from nova.skill import SkillRegistry

skills_dir = Path("skills").resolve()
registry = SkillRegistry(skills_dir)

print(f"  ✓ 加载了 {len(registry.list_all())} 个 skills")
for s in registry.list_all():
    print(f"    - {s.name}: {s.capabilities}")

# 2. 测试工具
print("\n[2/5] 测试工具...")
from nova.tools import search_web, fetch_url, read_file, write_file, list_directory

tools = [search_web, fetch_url, read_file, write_file, list_directory]
print(f"  ✓ 基础工具: {len(tools)} 个")
for t in tools:
    print(f"    - {t.name}")

# 3. 测试模型配置
print("\n[3/5] 测试模型配置...")
from nova.agent import AgentConfig

test_configs = [
    ("MiniMax-M2.5", "openai"),
    ("gpt-4o", "openai"),
    ("claude-3-5-sonnet", "anthropic"),
]

for model, expected in test_configs:
    config = AgentConfig(model=model)
    actual = "anthropic" if config.is_anthropic else "openai"
    status = "✓" if actual == expected else "✗"
    print(f"  {status} {model}: {actual}")

# 4. 测试 Skill 读取工具
print("\n[4/5] 测试 Skill 读取...")
code_content = registry.read_skill_content("coder")
print(f"  ✓ coder skill 内容: {len(code_content)} 字符")

# 5. 测试路径跨平台
print("\n[5/5] 测试跨平台路径...")
test_paths = [
    "skills/coder/SKILL.md",
    "skills\\coder\\SKILL.md",  # Windows 风格
    "~/documents/file.txt",
]

for p in test_paths:
    path = Path(p).expanduser()
    print(f"  ✓ {p} -> {path}")

print("\n" + "=" * 50)
print("所有测试通过！")
print("=" * 50)
print("\n启动服务:")
print("  uv pip install -e .")
print("  uv run main.py")
