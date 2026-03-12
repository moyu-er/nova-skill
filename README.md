# Nova Skill

轻量级 Skill + Tool 框架，基于 LangChain / LangGraph

## 特性

- ✅ 轻量级设计，核心代码 < 600 行
- ✅ 基于 LangChain / LangGraph 框架能力
- ✅ **Skills 使用 Markdown 格式定义**（SKILL.md）
- ✅ Skills 的 system_prompt 自动注入到 Agent
- ✅ 跨平台支持（Windows / Linux / macOS）
- ✅ uv 虚拟环境管理
- ✅ 预留 MCP 扩展接口

## 快速开始

### 1. 安装依赖（使用 uv）

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境
uv venv

# 安装依赖
uv pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，设置 OPENAI_API_KEY
```

### 3. 运行

```bash
uv run main.py
```

## Skill 定义格式

Skills 使用 **Markdown 文件**定义，位于 `skills/{skill_name}/SKILL.md`：

```markdown
# Skill 标题

## 描述
技能的详细描述...

## 能力标签
- tag1
- tag2

## 代码规范
- 语言: python
- 库: xxx

## 输出格式
1. 步骤一
2. 步骤二

## 注意事项
- 注意点 1
- 注意点 2

## 代码示例

### 示例 1

```python
# 示例代码
print("hello")
```
```

## 项目结构

```
nova-skill/
├── src/nova/           # 核心代码
│   ├── __init__.py
│   ├── skill.py        # Skill 定义和 Markdown 解析
│   └── agent.py        # LangGraph Agent
├── skills/             # Skill 定义文件（Markdown）
│   ├── coder/          
│   │   └── SKILL.md    # Python 代码生成 Skill
│   └── data_analyst/
│       └── SKILL.md    # 数据分析 Skill
├── main.py             # 启动脚本
├── pyproject.toml      # uv 配置
└── requirements.txt    # 依赖列表
```

## Skill 加载流程

1. **扫描**: 扫描 `skills/` 目录下的所有子目录
2. **解析**: 读取 `SKILL.md`，提取：
   - 描述 → system_prompt
   - 能力标签 → 用于匹配 Agent
   - 代码规范 → system_prompt
   - 输出格式 → system_prompt
   - 注意事项 → system_prompt
   - 代码示例 → few-shot
3. **注册**: 注册到 SkillRegistry
4. **注入**: Agent 启动时合并所有 skill 的 system_prompt

## 跨平台兼容

代码自动检测操作系统：

- **Windows**: 使用 `subprocess` 替代 `resource` 模块
- **Linux/macOS**: 正常使用系统特性

## 后续扩展

- [ ] MCP (Model Context Protocol) 支持
- [ ] 更多内置 Tools
- [ ] Web UI
- [ ] 多模型支持
