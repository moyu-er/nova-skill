# Nova Skill

轻量级 Skill + Tool 框架，支持 OpenAI / Anthropic 模型，提供交互式 CLI 和 FastAPI 后端两种使用方式。

## 项目结构

```
nova-skill/
├── cli.py              # 交互式命令行界面（推荐日常使用）
├── main.py             # FastAPI 后端服务
├── src/nova/           # 核心框架代码
│   ├── agent.py        # Agent 实现
│   ├── skill.py        # Skill 管理
│   └── tools.py        # 工具注册
├── skills/             # Skill 定义目录
│   ├── antfu/          # Anthony Fu 开发规范
│   ├── brainstorming/  # 头脑风暴
│   └── writing-skills/ # 写作技巧
├── scripts/            # 构建脚本
│   ├── build.py        # 打包脚本
│   └── nova-cli.spec   # PyInstaller 配置
├── release/            # 打包后的可执行文件
├── tests/              # 测试文件
├── .env.example        # 环境变量模板
├── pyproject.toml      # 项目配置
└── requirements.txt    # 依赖列表
```

## 特性

✅ **双模式支持** - 交互式 CLI + FastAPI 后端服务  
✅ **ReAct 流式输出** - 实时显示 AI 思考过程和工具调用  
✅ **多模型支持** - OpenAI / Anthropic / 其他兼容模型  
✅ **框架能力** - 使用 LangChain `@tool` 装饰器自动注册工具  
✅ **Skill 系统** - 模型按需读取 skill 详细内容  
✅ **跨平台** - Windows / Linux / macOS  
✅ **日志记录** - loguru 日志管理

## 安装

### 方式一：使用 uv（推荐）

```bash
# 创建虚拟环境
uv venv

# 安装依赖
uv pip install -e ".[dev]"
```

### 方式二：使用 pip

```bash
pip install -r requirements.txt
```

### 方式三：打包为可执行文件

```bash
# 打包 CLI 为可执行文件
python scripts/build.py

# 输出位置: release/nova.exe (Windows) 或 release/nova (Linux/Mac)
```

## 配置

```bash
# 复制环境变量模板
cp .env.example .env
```

编辑 `.env`:

```env
# ===== 模型配置 =====

# 模型名称 (OpenAI: gpt-4o-mini, gpt-4o, etc. | Anthropic: claude-3-5-sonnet-20241022, etc.)
MODEL=gpt-4o-mini

# 温度参数 (0.0 - 2.0)
TEMPERATURE=0.7

# 强制指定模型类型 (auto | openai | anthropic)
DEFAULT_MODEL_TYPE=auto

# ===== OpenAI 配置 =====
OPENAI_API_KEY=sk-...
# OPENAI_BASE_URL=https://api.openai.com/v1  # 可选，用于第三方兼容

# ===== Anthropic 配置 =====
ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_BASE_URL=https://api.anthropic.com  # 可选，用于第三方兼容
```

## 使用方式

### 方式一：CLI 交互模式（推荐）

`cli.py` 提供交互式命令行界面，支持多轮对话和 ReAct 流式输出。

```bash
# 启动 CLI
python cli.py

# 或使用打包后的可执行文件
./release/nova.exe
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
| `/react` | 切换 ReAct 模式（开/关） |

**CLI 启动参数：**

```bash
# 指定模型
python cli.py --model gpt-4o

# 关闭 ReAct 模式
python cli.py --no-react
```

### 方式二：FastAPI 后端服务

`main.py` 提供 FastAPI 后端服务，支持 SSE 流式输出。

```bash
# 启动服务
python main.py

# 或使用 uvicorn 直接启动
uvicorn main:app --host 0.0.0.0 --port 8000
```

**API 端点：**

```bash
# 健康检查
curl http://localhost:8000/health

# 获取模型信息
curl http://localhost:8000/model

# 获取所有 skills
curl http://localhost:8000/skills

# 流式对话
curl -X POST "http://localhost:8000/chat?message=Hello"
```

## 工具（自动注册）

| 工具 | 描述 |
|------|------|
| `search_web` | 搜索网络信息（DuckDuckGo） |
| `fetch_url` | 获取网页内容 |
| `read_file` | 读取本地文件（跨平台） |
| `write_file` | 写入本地文件（跨平台） |
| `list_directory` | 列出目录内容 |
| `get_available_skills` | 获取可用 skills |
| `read_skill_detail` | 读取 skill 详细内容 |

## Skill 格式

Skills 存放在 `skills/` 目录下，每个 skill 是一个子目录，包含 `SKILL.md`：

```markdown
# Skill Name

## 描述

描述内容...

## 能力标签

- capability1
- capability2

## 代码规范

- 语言: python
- 库: xxx

## 输出格式

1. xxx
2. xxx

## 注意事项

- xxx
```

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

## 打包发布

```bash
# 打包为可执行文件
python scripts/build.py

# 清理并重新打包
python scripts/build.py --clean

# 只清理构建文件
python scripts/build.py --only-clean
```

打包后的文件位于 `release/` 目录，可直接复制到其他位置使用。

## 环境要求

- Python >= 3.10
- Windows / Linux / macOS

## 许可证

MIT
