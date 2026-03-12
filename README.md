# Nova Skill

轻量级 Skill + Tool 框架，支持 OpenAI / Anthropic

## 特性

✅ **框架能力** - 使用 LangChain `@tool` 装饰器自动注册工具  
✅ **多模型支持** - OpenAI / Anthropic / 其他兼容模型  
✅ **纯后端流式** - SSE 格式输出  
✅ **跨平台** - Windows / Linux / macOS  
✅ **工具丰富** - search_web, fetch_url, read_file, write_file, list_directory  
✅ **Skill 读取** - 模型按需读取 skill 详细内容  
✅ **日志记录** - loguru

## 安装

```bash
# 使用 uv
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
# OpenAI
OPENAI_API_KEY=sk-...
MODEL=gpt-4o-mini

# 或 Anthropic
ANTHROPIC_API_KEY=sk-ant-...
MODEL=claude-3-5-sonnet-20241022
```

## 运行

```bash
uv run main.py
```

## API

```bash
# 健康检查
curl http://localhost:8000/health

# 流式对话
curl -X POST "http://localhost:8000/chat?message=Hello"
```

## 工具（自动注册）

| 工具 | 描述 |
|------|------|
| `search_web` | 搜索网络信息 |
| `fetch_url` | 获取网页内容 |
| `read_file` | 读取本地文件（跨平台） |
| `write_file` | 写入本地文件（跨平台） |
| `list_directory` | 列出目录内容 |
| `get_available_skills` | 获取可用 skills |
| `read_skill_detail` | 读取 skill 详细内容 |

## Skill 格式

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
