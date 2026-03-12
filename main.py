#!/usr/bin/env python3
"""
Nova Skill - FastAPI 后端

特性：
- 支持 OpenAI / Anthropic / 其他模型
- 纯后端流式输出（SSE）
- 跨平台兼容
- 使用 LangChain @tool 装饰器（框架能力）
"""
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:MM:SS} | {level} | {message}")
logger.add("logs/nova.log", rotation="10 MB", retention="7 days")

# 加载环境变量
load_dotenv()

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from nova.skill import SkillRegistry
from nova.agent import Agent, AgentConfig


# 全局变量
agent = None
skill_registry = None


def get_model_config() -> tuple:
    """
    获取模型配置
    
    支持 OPENAI_ 和 ANTHROPIC_ 前缀的环境变量
    通过 DEFAULT_MODEL_TYPE 可以强制指定模型类型
    """
    # 获取模型类型配置 (openai | anthropic | auto)
    model_type = os.getenv("DEFAULT_MODEL_TYPE", "auto").lower().strip()
    
    # 获取温度参数
    try:
        temperature = float(os.getenv("TEMPERATURE", "0.7"))
    except ValueError:
        logger.warning("Invalid TEMPERATURE value, using default 0.7")
        temperature = 0.7
    
    # 获取模型名称
    model = os.getenv("MODEL", "gpt-4o-mini")
    
    # 根据模型类型或模型名称确定 provider
    is_anthropic = False
    if model_type == "anthropic":
        is_anthropic = True
        logger.info(f"Using forced Anthropic model type: {model}")
    elif model_type == "openai":
        is_anthropic = False
        logger.info(f"Using forced OpenAI model type: {model}")
    else:
        # auto mode: detect from model name
        is_anthropic = "claude" in model.lower()
        provider = "Anthropic" if is_anthropic else "OpenAI-compatible"
        logger.info(f"Auto-detected {provider} model: {model}")
    
    if is_anthropic:
        # Anthropic 配置
        api_key = os.getenv("ANTHROPIC_API_KEY")
        base_url = os.getenv("ANTHROPIC_BASE_URL")  # 可选，用于第三方兼容
        
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        
        return model, api_key, base_url, temperature, "anthropic"
    
    else:
        # OpenAI 或其他兼容模型 (默认)
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")  # 可选，用于第三方兼容
        
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        
        return model, api_key, base_url, temperature, "openai"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global agent, skill_registry
    
    logger.info("🚀 Starting Nova Skill...")
    
    # 获取模型配置
    model, api_key, base_url, temperature, model_type = get_model_config()
    
    # 跨平台路径处理
    skills_dir = Path(__file__).parent / "skills"
    logger.info(f"Skills directory: {skills_dir}")
    
    # 加载 Skills
    logger.info("Loading skills...")
    skill_registry = SkillRegistry(skills_dir)
    
    # 创建 Agent
    logger.info("Creating agent...")
    config = AgentConfig(
        name="nova",
        model=model,
        temperature=temperature,
        model_type=model_type,
        skills=["coder"] if skill_registry.get("coder") else []
    )
    
    agent = Agent(
        config=config,
        skill_registry=skill_registry,
        api_key=api_key,
        base_url=base_url
    )
    
    logger.info("✅ Nova Skill ready!")
    yield
    
    logger.info("👋 Shutting down...")


# 创建 FastAPI 应用
app = FastAPI(
    title="Nova Skill API",
    description="支持 OpenAI / Anthropic 的 Skill + Tool 框架",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "agent": agent is not None,
        "model": agent.config.model if agent else None
    }


@app.get("/model")
async def get_model_info():
    """获取当前模型信息"""
    if not agent:
        return {"error": "Agent not initialized"}
    
    return {
        "model": agent.config.model,
        "provider": "anthropic" if agent.config.is_anthropic else "openai",
        "model_type": agent.config.model_type,
        "temperature": agent.config.temperature,
        "skills_loaded": [s.name for s in agent._skills_loaded]
    }


@app.get("/skills")
async def list_skills():
    """列出所有 skills"""
    if not skill_registry:
        return {"skills": []}
    
    skills = []
    for s in skill_registry.list_all():
        skills.append({
            "name": s.name,
            "description": s.description[:100] if s.description else "",
            "capabilities": s.capabilities
        })
    
    return {"skills": skills}


@app.post("/chat")
async def chat(message: str):
    """
    流式对话
    
    返回 SSE 格式流
    """
    if not agent:
        return StreamingResponse(
            iter(["data: Agent not initialized\n\n"]),
            media_type="text/event-stream"
        )
    
    async def event_generator():
        try:
            async for chunk in agent.astream(message):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: Error: {e}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
