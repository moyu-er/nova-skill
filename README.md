# Nova Skill

轻量级 AI Agent 框架，支持 OpenAI / Anthropic 模型，提供交互式 CLI 和任务规划能力。

## 项目结构

```
nova-skill/
├── cli.py              # 交互式命令行界面（主入口）
├── src/                # 核心框架代码
│   ├── agent/          # Agent 实现
│   │   └── agent.py    # ReAct 流式 Agent
│   ├── core/           # 核心类型定义
│   │   └── types.py    # ModelType, Event 类型等
│   ├── display/        # 终端显示组件
│   │   └── progress.py # 进度显示
│   ├── skills/         # Skill 系统
│   │   └── registry.py # Skill 注册管理
│   ├── tasks/          # 任务规划
│   │   ├── manager.py  # 任务管理器
│   │   └── planner.py  # 任务规划工具
│   └── tools/          # 工具集合
│       ├── __init__.py # 工具自动发现
│       ├── files.py    # 文件操作（mmap 优化）
│       ├── network.py  # 网络请求
│       ├── system.py   # 系统信息
│       ├── time.py     # 时间工具
│       ├── skills.py   # Skill 工具
│       └── tasks.py    # 任务工具
├── skills/             # Skill 定义目录
│   ├── antfu/          # Anthony Fu 开发规范
│   ├── brainstorming/  # 头脑风暴
│   └── writing-skills/ # 写作技巧
├── tests/              # 测试文件
├── .env.example        # 环境变量模板
└── pyproject.toml      # 项目配置
```

## 特性

✅ **ReAct 流式输出** - 实时显示 AI 思考过程和工具调用  
✅ **多模型支持** - OpenAI / Anthropic / 其他兼容模型  
✅ **自动工具发现** - 使用 `@tool` 装饰器自动注册工具  
✅ **Skill 系统** - 模型按需读取 skill 详细内容  
✅ **任务规划** - 支持复杂多步骤任务分解和跟踪  
✅ **mmap 文件读取** - 高效的大文件随机访问  
✅ **跨平台** - Windows / Linux / macOS  
✅ **内存会话** - 基于 LangGraph 的内存检查点

## 安装

```bash
# 使用 uv（推荐）
uv venv
uv pip install -e ".[dev]"

# 或使用 pip
pip install -r requirements.txt
```

## 配置

```bash
cp .env.example .env
```

编辑 `.env`:

```env
# 模型配置
MODEL=gpt-4o-mini
TEMPERATURE=0.7
DEFAULT_MODEL_TYPE=auto

# OpenAI
OPENAI_API_KEY=sk-...
# OPENAI_BASE_URL=https://api.openai.com/v1

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_BASE_URL=https://api.anthropic.com
```

## 使用方式

### CLI 交互模式

```bash
# 启动 CLI
python cli.py

# 指定模型
python cli.py --model gpt-4o

# 关闭 ReAct 模式
python cli.py --no-react
```

**CLI 命令：**

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/quit` | 退出程序 |
| `/clear` | 清屏 |
| `/skills` | 显示已加载的 skills |
| `/tools` | 显示已注册的工具 |
| `/model` | 显示当前模型信息 |
| `/react` | 切换 ReAct 模式 |
| `/plan` | 创建任务计划 |
| `/tasks` | 显示任务计划状态 |

## 工具列表

| 工具 | 描述 |
|------|------|
| `read_file` | 读取文件（支持行范围，mmap 优化） |
| `write_file` | 写入文件 |
| `list_directory` | 列出目录 |
| `get_file_info` | 获取文件信息 |
| `execute_command` | 执行系统命令 |
| `get_system_info` | 获取系统信息 |
| `get_current_time` | 获取当前时间 |
| `fetch_url` | 获取网页内容 |
| `get_available_skills` | 获取可用 skills |
| `read_skill_detail` | 读取 skill 详细内容 |
| `create_task_plan` | 创建任务计划 |
| `get_task_status` | 获取任务状态 |
| `update_task_status` | 更新任务状态 |

## 开发

### 运行测试

```bash
pytest
```

### 代码格式化

```bash
ruff check .
ruff format .
```

## 环境要求

- Python >= 3.10
- Windows / Linux / macOS

## 许可证

MIT
